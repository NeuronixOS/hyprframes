#include "ImgBorder.hpp"
#include "ImgBorderPassElement.hpp"
#include "globals.hpp"
#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/desktop/DesktopTypes.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/helpers/Color.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/decorations/DecorationPositioner.hpp>
#include <hyprutils/math/Box.hpp>
#include <hyprutils/math/Vector2D.hpp>
#include <GLES3/gl32.h>
#include <algorithm>
#include <cmath>
#include <exception>

using namespace GL;
using namespace Render;

CImgBorder::CImgBorder(PHLWINDOW pWindow) : IHyprWindowDecoration(pWindow) {
  m_window = pWindow;
  // Copy POD only. Never repositionDeco from the ctor.
  if (g_pGlobalState) {
    const auto &s = g_pGlobalState->settings;
    for (int i = 0; i < 4; i++) {
      m_sizes[i] = s.sizes[i];
      m_insets[i] = s.insets[i];
    }
    m_scale = s.scale;
    m_shouldSmooth = s.smooth;
    m_shouldBlur = s.blur;
  }
}

CImgBorder::~CImgBorder() = default;

void CImgBorder::applySettings() {
  if (!g_pGlobalState)
    return;
  const auto &s = g_pGlobalState->settings;
  for (int i = 0; i < 4; i++) {
    m_sizes[i] = s.sizes[i];
    m_insets[i] = s.insets[i];
  }
  m_scale = s.scale;
  m_shouldSmooth = s.smooth;
  m_shouldBlur = s.blur;
  if (g_pDecorationPositioner)
    g_pDecorationPositioner->repositionDeco(this);
  damageEntire();
}

PHLWINDOW CImgBorder::window() const { return m_window; }

SDecorationPositioningInfo CImgBorder::getPositioningInfo() {
  SDecorationPositioningInfo info;
  info.policy = DECORATION_POSITION_STICKY;
  info.edges = DECORATION_EDGE_LEFT | DECORATION_EDGE_RIGHT |
               DECORATION_EDGE_TOP | DECORATION_EDGE_BOTTOM;
  info.priority = 4999;
  info.reserved = true;
    if (g_pGlobalState && g_pGlobalState->textures.ready) {
    info.desiredExtents = {
        .topLeft = {(m_sizes[0] - m_insets[0]) * m_scale,
                    (m_sizes[2] - m_insets[2]) * m_scale},
        .bottomRight = {(m_sizes[1] - m_insets[1]) * m_scale,
                        (m_sizes[3] - m_insets[3]) * m_scale},
    };
  }
  return info;
}

void CImgBorder::onPositioningReply(const SDecorationPositioningReply &reply) {
  m_assignedBox = reply.assignedGeometry;
}

void CImgBorder::draw(PHLMONITOR pMonitor, const float &a) {
  if (!pMonitor || !g_pGlobalState)
    return;

  try {
    hyprframesEnsureTextures();
  } catch (...) {
    return;
  }

  if (!g_pGlobalState->textures.ready)
    return;

  const auto PWINDOW = window();
  if (!validMapped(PWINDOW) || !PWINDOW->m_ruleApplicator ||
      !PWINDOW->m_ruleApplicator->decorate().valueOrDefault())
    return;

  CImgBorderPassElement::SData data = {.deco = this, .a = a};
  g_pHyprRenderer->m_renderPass.add(makeUnique<CImgBorderPassElement>(data));
}

eDecorationType CImgBorder::getDecorationType() { return DECORATION_CUSTOM; }

void CImgBorder::updateWindow(PHLWINDOW) { damageEntire(); }

void CImgBorder::damageEntire() {
  if (!g_pHyprRenderer)
    return;
  const auto box = getGlobalBoundingBox();
  if (box.w > 0 && box.h > 0)
    g_pHyprRenderer->damageBox(box);
}

eDecorationLayer CImgBorder::getDecorationLayer() {
  return DECORATION_LAYER_OVER;
}

uint64_t CImgBorder::getDecorationFlags() {
  return DECORATION_PART_OF_MAIN_WINDOW;
}

std::string CImgBorder::getDisplayName() { return DISPLAY_NAME; }

bool CImgBorder::shouldBlur() const { return m_shouldBlur; }

CBox CImgBorder::getGlobalBoundingBox() {
  const auto PWINDOW = window();
  if (!PWINDOW || !g_pDecorationPositioner)
    return {};

  CBox box = m_assignedBox;
  box.translate(g_pDecorationPositioner->getEdgeDefinedPoint(
      DECORATION_EDGE_TOP | DECORATION_EDGE_LEFT, PWINDOW));

  const auto PWORKSPACE = PWINDOW->m_workspace;
  const auto WORKSPACEOFFSET = PWORKSPACE && !PWINDOW->m_pinned
                                   ? PWORKSPACE->m_renderOffset->value()
                                   : Vector2D();

  return box.translate(WORKSPACEOFFSET);
}

static void drawSlice(SP<ITexture> tex, const CBox &box, float a, bool blur,
                      bool repeat, Vector2D uvTL, Vector2D uvBR) {
  if (!tex || tex->m_texID == 0 || !g_pHyprOpenGL || box.w <= 0 || box.h <= 0)
    return;
  if (!std::isfinite(box.x) || !std::isfinite(box.y) || !std::isfinite(box.w) ||
      !std::isfinite(box.h) || !std::isfinite(a))
    return;

  const bool cropped = uvTL.x > 0.001 || uvTL.y > 0.001 || uvBR.x < 0.999 ||
                       uvBR.y < 0.999;
  CHyprOpenGLImpl::STextureRenderData data;
  data.a = a;
  data.blur = blur;
  data.allowCustomUV = repeat || cropped;
  data.wrapX = repeat ? GL_REPEAT : GL_CLAMP_TO_EDGE;
  data.wrapY = repeat ? GL_REPEAT : GL_CLAMP_TO_EDGE;
  data.discardMode = DISCARD_ALPHA;
  if (repeat || cropped) {
    if (!std::isfinite(uvTL.x) || !std::isfinite(uvTL.y) ||
        !std::isfinite(uvBR.x) || !std::isfinite(uvBR.y) || uvBR.x <= uvTL.x ||
        uvBR.y <= uvTL.y)
      return;
    data.primarySurfaceUVTopLeft = uvTL;
    data.primarySurfaceUVBottomRight = uvBR;
  }
  g_pHyprOpenGL->renderTexture(tex, box, data);
}

static void drawLine(const CBox &box, float a) {
  if (!g_pGlobalState || !g_pHyprOpenGL || box.w <= 0.f || box.h <= 0.f)
    return;
  const float *c = g_pGlobalState->settings.line;
  if (c[3] <= 0.f)
    return;
  g_pHyprOpenGL->renderRect(
      box, CHyprColor{c[0], c[1], c[2], c[3] * a}, {});
}

static float graphicLen(const SP<ITexture> &tex, bool horizontal, float thick);

// Repeat the tile at its own size. Each draw covers at most a few copies so
// the texture coordinate stays small; one huge GL_REPEAT span crashes the iGPU.
static constexpr float kMaxRepeat = 8.f;

static void drawRepeat(SP<ITexture> tex, float x, float y, float along,
                       float cross, bool horizontal, float a, bool blur) {
  if (!tex || along <= 0.f || cross <= 0.f)
    return;
  const float unit = graphicLen(tex, horizontal, cross);
  if (!(unit > 0.5f))
    return;
  float done = 0.f;
  while (done < along - 0.25f) {
    const float room = along - done;
    const float span = std::min(room, unit * kMaxRepeat);
    if (span <= 0.25f)
      break;
    const float reps = span / unit;
    Vector2D uvTL{0., 0.}, uvBR{1., 1.};
    if (horizontal)
      uvBR.x = reps;
    else
      uvBR.y = reps;
    const CBox box = horizontal ? CBox{{x + done, y}, {span, cross}}
                                : CBox{{x, y + done}, {cross, span}};
    drawSlice(tex, box, a, blur, true, uvTL, uvBR);
    done += span;
  }
}

// Length of the graphic at the corner's thickness. Never longer than the
// picture itself, so a wider window lengthens the connecting line instead.
static float graphicLen(const SP<ITexture> &tex, bool horizontal, float thick) {
  if (!tex || thick <= 0.f)
    return 0.f;
  const float along = horizontal ? static_cast<float>(tex->m_size.x)
                                 : static_cast<float>(tex->m_size.y);
  const float cross = horizontal ? static_cast<float>(tex->m_size.y)
                                 : static_cast<float>(tex->m_size.x);
  if (along <= 0.f || cross <= 0.f)
    return 0.f;
  return along * (thick / cross);
}

static void drawGraphic(SP<ITexture> tex, float x, float y, float along,
                        float cross, bool horizontal, float a, bool blur) {
  if (!tex || along <= 0.f || cross <= 0.f)
    return;
  const float full = graphicLen(tex, horizontal, cross);
  float span = 1.f;
  float off = 0.f;
  if (full > along && full > 0.f) {
    span = along / full;
    off = (1.f - span) * 0.5f;
  }
  Vector2D uvTL{0., 0.}, uvBR{1., 1.};
  if (horizontal) {
    uvTL.x = off;
    uvBR.x = off + span;
  } else {
    uvTL.y = off;
    uvBR.y = off + span;
  }
  const CBox box = horizontal ? CBox{{x, y}, {along, cross}}
                              : CBox{{x, y}, {cross, along}};
  drawSlice(tex, box, a, blur, false, uvTL, uvBR);
}

static void fitTrio(float &a, float &b, float &c, float limit) {
  const float need = a + b + c;
  if (need <= limit || need <= 0.f)
    return;
  const float k = limit / need;
  a *= k;
  b *= k;
  c *= k;
}

static void drawEdgeH(SP<ITexture> center, SP<ITexture> flankL,
                      SP<ITexture> flankR, SP<ITexture> tile, float x, float y,
                      float width, float thick, float a, bool blur) {
  if (width <= 0 || thick <= 0)
    return;

  float fL = graphicLen(flankL, true, thick);
  float fR = graphicLen(flankR, true, thick);
  float cW = graphicLen(center, true, thick);
  fitTrio(fL, cW, fR, width);

  const float innerX = x + fL;
  const float innerW = width - fL - fR;
  if (innerW > 0.f) {
    if (tile)
      drawRepeat(tile, innerX, y, innerW, thick, true, a, blur);
    else
      drawLine({{innerX, y}, {innerW, thick}}, a);
  }
  if (fL > 0.f)
    drawGraphic(flankL, x, y, fL, thick, true, a, blur);
  if (fR > 0.f)
    drawGraphic(flankR, x + width - fR, y, fR, thick, true, a, blur);
  if (cW <= 0.f || innerW <= 0.f)
    return;
  const float shown = std::min(cW, innerW);
  drawGraphic(center, innerX + (innerW - shown) * 0.5f, y, shown, thick, true,
              a, blur);
}

static void drawEdgeV(SP<ITexture> center, SP<ITexture> flankT,
                      SP<ITexture> flankB, SP<ITexture> tile, float x, float y,
                      float thick, float length, float a, bool blur) {
  if (thick <= 0 || length <= 0)
    return;

  float fT = graphicLen(flankT, false, thick);
  float fB = graphicLen(flankB, false, thick);
  float cH = graphicLen(center, false, thick);
  fitTrio(fT, cH, fB, length);

  const float innerY = y + fT;
  const float innerH = length - fT - fB;
  if (innerH > 0.f) {
    if (tile)
      drawRepeat(tile, x, innerY, innerH, thick, false, a, blur);
    else
      drawLine({{x, innerY}, {thick, innerH}}, a);
  }
  if (fT > 0.f)
    drawGraphic(flankT, x, y, fT, thick, false, a, blur);
  if (fB > 0.f)
    drawGraphic(flankB, x, y + length - fB, fB, thick, false, a, blur);
  if (cH <= 0.f || innerH <= 0.f)
    return;
  const float shown = std::min(cH, innerH);
  drawGraphic(center, x, innerY + (innerH - shown) * 0.5f, shown, thick, false,
              a, blur);
}

void CImgBorder::drawPass(PHLMONITOR pMonitor, const float &a) {
  const auto PWINDOW = window();
  if (!pMonitor || !validMapped(PWINDOW) || !g_pGlobalState ||
      !g_pGlobalState->textures.ready)
    return;

  try {
    const auto &tex = g_pGlobalState->textures;

    auto box = getGlobalBoundingBox()
                   .translate(PWINDOW->m_floatingOffset - pMonitor->m_position)
                   .scale(pMonitor->m_scale);

    const auto scale = m_scale * pMonitor->m_scale;

    const float borderL = std::max(0.f, (float)(m_sizes[0] - m_insets[0]) * scale);
    const float borderR = std::max(0.f, (float)(m_sizes[1] - m_insets[1]) * scale);
    const float borderT = std::max(0.f, (float)(m_sizes[2] - m_insets[2]) * scale);
    const float borderB = std::max(0.f, (float)(m_sizes[3] - m_insets[3]) * scale);

    const auto HEIGHT_MID = box.height - borderT - borderB;
    const auto WIDTH_MID = box.width - borderL - borderR;
    if (HEIGHT_MID <= 0 || WIDTH_MID <= 0)
      return;

    const auto wasUsingNearestNeighbour =
        g_pHyprRenderer->m_renderData.useNearestNeighbor;
    g_pHyprRenderer->m_renderData.useNearestNeighbor = !m_shouldSmooth;

    const bool blur = shouldBlur();

    drawEdgeH(tex.tc, tex.tfl, tex.tfr, tex.t, box.x + borderL, box.y,
              WIDTH_MID, borderT, a, blur);
    drawEdgeH(tex.bc, tex.bfl, tex.bfr, tex.b, box.x + borderL,
              box.y + box.height - borderB, WIDTH_MID, borderB, a, blur);
    drawEdgeV(tex.lc, tex.lft, tex.lfb, tex.l, box.x, box.y + borderT, borderL,
              HEIGHT_MID, a, blur);
    drawEdgeV(tex.rc, tex.rft, tex.rfb, tex.r, box.x + box.width - borderR,
              box.y + borderT, borderR, HEIGHT_MID, a, blur);

    if (tex.tl)
      drawSlice(tex.tl, {box.pos(), {borderL, borderT}}, a, blur, false, {0., 0.},
                {1., 1.});
    if (tex.tr)
      drawSlice(tex.tr,
                {{box.x + box.width - borderR, box.y}, {borderR, borderT}}, a,
                blur, false, {0., 0.}, {1., 1.});
    if (tex.br)
      drawSlice(tex.br,
                {{box.x + box.width - borderR, box.y + box.height - borderB},
                 {borderR, borderB}},
                a, blur, false, {0., 0.}, {1., 1.});
    if (tex.bl)
      drawSlice(tex.bl,
                {{box.x, box.y + box.height - borderB}, {borderL, borderB}}, a,
                blur, false, {0., 0.}, {1., 1.});

    g_pHyprRenderer->m_renderData.useNearestNeighbor = wasUsingNearestNeighbour;
  } catch (...) {
  }
}
