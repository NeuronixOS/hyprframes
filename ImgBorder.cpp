#include "ImgBorder.hpp"
#include "ImgBorderPassElement.hpp"
#include "Log.hpp"
#include "globals.hpp"
#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/desktop/DesktopTypes.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/decorations/DecorationPositioner.hpp>
#include <hyprutils/math/Box.hpp>
#include <hyprutils/math/Vector2D.hpp>
#include <GLES3/gl32.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <exception>

using namespace GL;
using namespace Render;

namespace {
std::atomic<int> g_drawPassLogs{0};
}

CImgBorder::CImgBorder(PHLWINDOW pWindow) : IHyprWindowDecoration(pWindow) {
  m_window = pWindow;
  // Copy POD only. Never repositionDeco from the ctor.
  ImgLog::stage("CImgBorder.ctor");
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
  ImgLog::log("CImgBorder constructed");
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
    ImgLog::stageQuiet("draw.ensureTextures");
    imgbordersEnsureTextures();
  } catch (const std::exception &e) {
    ImgLog::log("ERROR draw ensureTextures: %s", e.what());
    return;
  } catch (...) {
    ImgLog::log("ERROR draw ensureTextures unknown");
    return;
  }

  if (!g_pGlobalState->textures.ready)
    return;

  const auto PWINDOW = window();
  if (!validMapped(PWINDOW) || !PWINDOW->m_ruleApplicator ||
      !PWINDOW->m_ruleApplicator->decorate().valueOrDefault())
    return;

  ImgLog::stageQuiet("draw.queuePass");
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
                      bool repeat, Vector2D uvBR) {
  if (!tex || tex->m_texID == 0 || !g_pHyprOpenGL || box.w <= 0 || box.h <= 0)
    return;
  if (!std::isfinite(box.x) || !std::isfinite(box.y) || !std::isfinite(box.w) ||
      !std::isfinite(box.h) || !std::isfinite(a))
    return;

  CHyprOpenGLImpl::STextureRenderData data;
  data.a = a;
  data.blur = blur;
  data.allowCustomUV = repeat;
  data.wrapX = repeat ? GL_REPEAT : GL_CLAMP_TO_EDGE;
  data.wrapY = repeat ? GL_REPEAT : GL_CLAMP_TO_EDGE;
  data.discardMode = DISCARD_ALPHA;
  if (repeat) {
    if (!std::isfinite(uvBR.x) || !std::isfinite(uvBR.y) || uvBR.x <= 0.f ||
        uvBR.y <= 0.f)
      return;
    uvBR.x = std::clamp(uvBR.x, 0.01, 64.0);
    uvBR.y = std::clamp(uvBR.y, 0.01, 64.0);
    data.primarySurfaceUVTopLeft = {0, 0};
    data.primarySurfaceUVBottomRight = uvBR;
  }
  g_pHyprOpenGL->renderTexture(tex, box, data);
}

// Center motif is drawn once at its natural scaled size (not stretched across
// half the window). Stretching/repeating a unique plaque with huge UV spans
// has hung the Intel GPU → Hyprland watchdog SIGKILL (no crash report).
static float fixedLen(const SP<ITexture> &tex, float axis, float scale,
                      float limit) {
  if (!tex || axis <= 0.f || scale <= 0.f || limit <= 0.f)
    return 0.f;
  return std::min(axis * scale, limit);
}

// [flank][tile…][center][…tile][flank]
static void drawEdgeH(SP<ITexture> tile, SP<ITexture> center,
                      SP<ITexture> flankL, SP<ITexture> flankR, float x,
                      float y, float width, float height, float /*windowSpan*/,
                      float scale, float a, bool blur) {
  if (width <= 0 || height <= 0)
    return;

  const float fL =
      fixedLen(flankL, flankL ? flankL->m_size.x : 0.f, scale, width * 0.5f);
  const float fR = fixedLen(flankR, flankR ? flankR->m_size.x : 0.f, scale,
                            std::max(0.f, width - fL));
  if (fL > 0.f)
    drawSlice(flankL, {{x, y}, {fL, height}}, a, blur, false, {1., 1.});
  if (fR > 0.f)
    drawSlice(flankR, {{x + width - fR, y}, {fR, height}}, a, blur, false,
              {1., 1.});

  const float innerX = x + fL;
  const float innerW = width - fL - fR;
  if (innerW <= 0.f)
    return;

  float centerW = 0.f;
  if (center && center->m_size.x > 0 && scale > 0)
    centerW = std::min((float)(center->m_size.x * scale), innerW);

  if (centerW <= 0.f) {
    if (!tile || tile->m_size.x <= 0)
      return;
    Vector2D uv = {1., 1.};
    if (scale > 0)
      uv.x = innerW / (tile->m_size.x * scale);
    drawSlice(tile, {{innerX, y}, {innerW, height}}, a, blur, true, uv);
    return;
  }

  const float side = (innerW - centerW) * 0.5f;
  if (tile && tile->m_size.x > 0 && side > 0.f) {
    Vector2D uv = {1., 1.};
    if (scale > 0)
      uv.x = side / (tile->m_size.x * scale);
    drawSlice(tile, {{innerX, y}, {side, height}}, a, blur, true, uv);
    drawSlice(tile, {{innerX + side + centerW, y}, {side, height}}, a, blur,
              true, uv);
  }
  drawSlice(center, {{innerX + side, y}, {centerW, height}}, a, blur, false,
            {1., 1.});
}

static void drawEdgeV(SP<ITexture> tile, SP<ITexture> center,
                      SP<ITexture> flankT, SP<ITexture> flankB, float x,
                      float y, float width, float height, float /*windowSpan*/,
                      float scale, float a, bool blur) {
  if (width <= 0 || height <= 0)
    return;

  const float fT =
      fixedLen(flankT, flankT ? flankT->m_size.y : 0.f, scale, height * 0.5f);
  const float fB = fixedLen(flankB, flankB ? flankB->m_size.y : 0.f, scale,
                            std::max(0.f, height - fT));
  if (fT > 0.f)
    drawSlice(flankT, {{x, y}, {width, fT}}, a, blur, false, {1., 1.});
  if (fB > 0.f)
    drawSlice(flankB, {{x, y + height - fB}, {width, fB}}, a, blur, false,
              {1., 1.});

  const float innerY = y + fT;
  const float innerH = height - fT - fB;
  if (innerH <= 0.f)
    return;

  float centerH = 0.f;
  if (center && center->m_size.y > 0 && scale > 0)
    centerH = std::min((float)(center->m_size.y * scale), innerH);

  if (centerH <= 0.f) {
    if (!tile || tile->m_size.y <= 0)
      return;
    Vector2D uv = {1., 1.};
    if (scale > 0)
      uv.y = innerH / (tile->m_size.y * scale);
    drawSlice(tile, {{x, innerY}, {width, innerH}}, a, blur, true, uv);
    return;
  }

  const float side = (innerH - centerH) * 0.5f;
  if (tile && tile->m_size.y > 0 && side > 0.f) {
    Vector2D uv = {1., 1.};
    if (scale > 0)
      uv.y = side / (tile->m_size.y * scale);
    drawSlice(tile, {{x, innerY}, {width, side}}, a, blur, true, uv);
    drawSlice(tile, {{x, innerY + side + centerH}, {width, side}}, a, blur,
              true, uv);
  }
  drawSlice(center, {{x, innerY + side}, {width, centerH}}, a, blur, false,
            {1., 1.});
}

void CImgBorder::drawPass(PHLMONITOR pMonitor, const float &a) {
  const int dlog = g_drawPassLogs.fetch_add(1);
  const bool verbose = dlog < 8;

  const auto PWINDOW = window();
  if (!pMonitor || !validMapped(PWINDOW) || !g_pGlobalState ||
      !g_pGlobalState->textures.ready)
    return;

  try {
    const auto &tex = g_pGlobalState->textures;

    ImgLog::stageQuiet("drawPass.box");
    auto box = getGlobalBoundingBox()
                   .translate(PWINDOW->m_floatingOffset - pMonitor->m_position)
                   .scale(pMonitor->m_scale);

    const auto scale = m_scale * pMonitor->m_scale;

    const auto BORDER_LEFT = (float)m_sizes[0] * scale;
    const auto BORDER_RIGHT = (float)m_sizes[1] * scale;
    const auto BORDER_TOP = (float)m_sizes[2] * scale;
    const auto BORDER_BOTTOM = (float)m_sizes[3] * scale;

    const auto HEIGHT_MID = box.height - BORDER_TOP - BORDER_BOTTOM;
    const auto WIDTH_MID = box.width - BORDER_LEFT - BORDER_RIGHT;
    if (HEIGHT_MID <= 0 || WIDTH_MID <= 0)
      return;

    if (verbose)
      ImgLog::log("drawPass #%d box=%.0fx%.0f mid=%.0fx%.0f", dlog, box.width,
                  box.height, WIDTH_MID, HEIGHT_MID);

    const auto wasUsingNearestNeighbour =
        g_pHyprRenderer->m_renderData.useNearestNeighbor;
    g_pHyprRenderer->m_renderData.useNearestNeighbor = !m_shouldSmooth;

    const bool blur = shouldBlur();

    ImgLog::stageQuiet("drawPass.corners");
    if (tex.tl)
      drawSlice(tex.tl, {box.pos(), {BORDER_LEFT, BORDER_TOP}}, a, blur, false,
                {1., 1.});
    if (tex.tr)
      drawSlice(tex.tr,
                {{box.x + box.width - BORDER_RIGHT, box.y},
                 {BORDER_RIGHT, BORDER_TOP}},
                a, blur, false, {1., 1.});
    if (tex.br)
      drawSlice(tex.br,
                {{box.x + box.width - BORDER_RIGHT,
                  box.y + box.height - BORDER_BOTTOM},
                 {BORDER_RIGHT, BORDER_BOTTOM}},
                a, blur, false, {1., 1.});
    if (tex.bl)
      drawSlice(tex.bl,
                {{box.x, box.y + box.height - BORDER_BOTTOM},
                 {BORDER_LEFT, BORDER_BOTTOM}},
                a, blur, false, {1., 1.});

    ImgLog::stageQuiet("drawPass.edgesH");
    drawEdgeH(tex.t, tex.tc, tex.tfl, tex.tfr, box.x + BORDER_LEFT, box.y,
              WIDTH_MID, BORDER_TOP, box.width, scale, a, blur);
    drawEdgeH(tex.b, tex.bc, tex.bfl, tex.bfr, box.x + BORDER_LEFT,
              box.y + box.height - BORDER_BOTTOM, WIDTH_MID, BORDER_BOTTOM,
              box.width, scale, a, blur);
    ImgLog::stageQuiet("drawPass.edgesV");
    drawEdgeV(tex.l, tex.lc, tex.lft, tex.lfb, box.x, box.y + BORDER_TOP,
              BORDER_LEFT, HEIGHT_MID, box.height, scale, a, blur);
    drawEdgeV(tex.r, tex.rc, tex.rft, tex.rfb, box.x + box.width - BORDER_RIGHT,
              box.y + BORDER_TOP, BORDER_RIGHT, HEIGHT_MID, box.height, scale,
              a, blur);

    g_pHyprRenderer->m_renderData.useNearestNeighbor = wasUsingNearestNeighbour;
    ImgLog::stageQuiet("idle");
  } catch (const std::exception &e) {
    ImgLog::log("ERROR drawPass: %s", e.what());
  } catch (...) {
    ImgLog::log("ERROR drawPass unknown");
  }
}
