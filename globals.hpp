#pragma once

#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/render/Texture.hpp>
#include <array>
#include <string>

using namespace Render;

inline HANDLE PHANDLE = nullptr;

// Plain POD + path buffer. No Hyprland Config::Values (they die on hyprbars reload).
// imagePath is a fixed buffer so we never copy a heap std::string on the draw path
// (that aborted Hyprland — crash reports 1379 / 2914).
struct SImgBorderSettings {
  char imagePath[512] =
      "/home/khinds/Projects/LinuxOS/ImageBorders/example.png";
  int sizes[4] = {5, 5, 5, 5};   // L R T B
  int insets[4] = {1, 1, 1, 1}; // L R T B
  float scale = 1.f;
  bool smooth = true;
  bool blur = false;
};

struct SGlobalTextures {
  SP<ITexture> tl, tr, br, bl, t, r, b, l;
  bool ready = false;
  bool failed = false;
};

struct SGlobalState {
  SImgBorderSettings settings;
  SGlobalTextures textures;
  uint32_t noImgBordersRuleIdx = 0;
};

// Defined in Settings.cpp — one object, not an inline header variable.
extern UP<SGlobalState> g_pGlobalState;

void imgbordersLoadSettings(SImgBorderSettings &out);
void imgbordersEnsureTextures();
