#include "ImgBorder.hpp"
#include "ImgBorderPassElement.hpp"
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

using namespace GL;
using namespace Render;

CImgBorder::CImgBorder(PHLWINDOW pWindow) : IHyprWindowDecoration(pWindow) {
  m_window = pWindow;
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

  // Lazy texture build once. Never copy std::string / settings structs here.
  try {
    imgbordersEnsureTextures();
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
                      bool repeat, Vector2D uvBR) {
  if (!tex || !g_pHyprOpenGL)
    return;

  CHyprOpenGLImpl::STextureRenderData data;
  data.a = a;
  data.blur = blur;
  data.allowCustomUV = repeat;
  data.wrapX = repeat ? GL_REPEAT : GL_CLAMP_TO_EDGE;
  data.wrapY = repeat ? GL_REPEAT : GL_CLAMP_TO_EDGE;
  data.discardMode = DISCARD_ALPHA;
  if (repeat) {
    data.primarySurfaceUVTopLeft = {0, 0};
    data.primarySurfaceUVBottomRight = uvBR;
  }
  g_pHyprOpenGL->renderTexture(tex, box, data);
}

void CImgBorder::drawPass(PHLMONITOR pMonitor, const float &a) {
  const auto PWINDOW = window();
  if (!pMonitor || !validMapped(PWINDOW) || !g_pGlobalState ||
      !g_pGlobalState->textures.ready)
    return;

  const auto &tex = g_pGlobalState->textures;

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

  const auto wasUsingNearestNeighbour =
      g_pHyprRenderer->m_renderData.useNearestNeighbor;
  g_pHyprRenderer->m_renderData.useNearestNeighbor = !m_shouldSmooth;

  const bool blur = shouldBlur();

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

  Vector2D uvX = {1., 1.};
  if (tex.t && tex.t->m_size.x != 0 && scale != 0)
    uvX.x = WIDTH_MID / (tex.t->m_size.x * scale);

  if (tex.t)
    drawSlice(tex.t, {{box.x + BORDER_LEFT, box.y}, {WIDTH_MID, BORDER_TOP}}, a,
              blur, true, uvX);
  if (tex.b)
    drawSlice(tex.b,
              {{box.x + BORDER_LEFT, box.y + box.height - BORDER_BOTTOM},
               {WIDTH_MID, BORDER_BOTTOM}},
              a, blur, true, uvX);

  Vector2D uvY = {1., 1.};
  if (tex.l && tex.l->m_size.y != 0 && scale != 0)
    uvY.y = HEIGHT_MID / (tex.l->m_size.y * scale);

  if (tex.l)
    drawSlice(tex.l, {{box.x, box.y + BORDER_TOP}, {BORDER_LEFT, HEIGHT_MID}},
              a, blur, true, uvY);
  if (tex.r)
    drawSlice(tex.r,
              {{box.x + box.width - BORDER_RIGHT, box.y + BORDER_TOP},
               {BORDER_RIGHT, HEIGHT_MID}},
              a, blur, true, uvY);

  g_pHyprRenderer->m_renderData.useNearestNeighbor = wasUsingNearestNeighbour;
}
