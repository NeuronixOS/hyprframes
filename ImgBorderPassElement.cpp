#include "ImgBorderPassElement.hpp"
#include "ImgBorder.hpp"
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/pass/PassElement.hpp>

using namespace Render::GL;

CImgBorderPassElement::CImgBorderPassElement(
    const CImgBorderPassElement::SData &data_) {
  data = data_;
}
CImgBorderPassElement::~CImgBorderPassElement() {}

std::vector<UP<IPassElement>> CImgBorderPassElement::draw() {
  if (!data.deco || !g_pHyprRenderer)
    return {};
  const auto mon = g_pHyprRenderer->m_renderData.pMonitor.lock();
  if (!mon)
    return {};
  data.deco->drawPass(mon, data.a);
  return {};
}

bool CImgBorderPassElement::needsLiveBlur() {
  return data.deco && data.deco->shouldBlur();
}

bool CImgBorderPassElement::needsPrecomputeBlur() {
  return data.deco && data.deco->shouldBlur();
}

const char *CImgBorderPassElement::passName() { return PASS_NAME; }

ePassElementType CImgBorderPassElement::type() { return EK_CUSTOM; }

// void CImgBorderPassElement::discard() {}

// bool CImgBorderPassElement::undiscardable() {}

std::optional<CBox> CImgBorderPassElement::boundingBox() {
  if (!data.deco || !g_pHyprRenderer)
    return std::nullopt;
  const auto mon = g_pHyprRenderer->m_renderData.pMonitor.lock();
  if (!mon)
    return std::nullopt;
  return data.deco->getGlobalBoundingBox().translate(-mon->m_position);
}

// CRegion CImgBorderPassElement::opaqueRegion() {}

// bool CImgBorderPassElement::disableSimplification() {}
