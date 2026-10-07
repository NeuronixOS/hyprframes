#pragma once

#include "globals.hpp"
#include <hyprland/src/desktop/DesktopTypes.hpp>
#include <hyprland/src/render/decorations/IHyprWindowDecoration.hpp>

using namespace Render;

static const auto DISPLAY_NAME = "Image borders";

class CImgBorder : public IHyprWindowDecoration {
public:
  CImgBorder(PHLWINDOW);
  virtual ~CImgBorder();

  virtual SDecorationPositioningInfo getPositioningInfo() override;
  virtual void
  onPositioningReply(const SDecorationPositioningReply &reply) override;
  virtual void draw(PHLMONITOR, float const &a) override;
  virtual eDecorationType getDecorationType() override;
  virtual void updateWindow(PHLWINDOW) override;
  virtual void damageEntire() override;
  virtual eDecorationLayer getDecorationLayer() override;
  virtual uint64_t getDecorationFlags() override;
  virtual std::string getDisplayName() override;

  bool shouldBlur() const;
  CBox getGlobalBoundingBox();
  void drawPass(PHLMONITOR, float const &a);
  // Pull latest POD settings from g_pGlobalState and re-layout.
  void applySettings();

private:
  PHLWINDOW window() const;

  PHLWINDOW m_window;
  CBox m_assignedBox;

  int m_sizes[4] = {0, 0, 0, 0};
  int m_insets[4] = {0, 0, 0, 0};
  float m_scale = 1.f;
  bool m_shouldSmooth = true;
  bool m_shouldBlur = false;
};
