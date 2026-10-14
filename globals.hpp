#pragma once

#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/render/Texture.hpp>
#include <array>
#include <string>

using namespace Render;

inline HANDLE PHANDLE = nullptr;

// Plain POD + path buffer. No Hyprland Config::Values (they die on hyprbars reload).
struct SImgBorderSettings {
  char imagePath[512] = "/usr/share/hyprframes/example.png";
  int sizes[4] = {5, 5, 5, 5};     // L R T B — corner / edge thickness in PNG px
  int insets[4] = {1, 1, 1, 1};   // L R T B
  // Center sample on each edge. 0 = no center (9-slice).
  // Order: top width, right height, bottom width, left height (PNG px).
  int centers[4] = {0, 0, 0, 0};
  // Fixed slice on each side of every corner, along the edge (21-patch).
  // Order matches centers. 0 = no corner-side slices (13-patch).
  int flanks[4] = {0, 0, 0, 0};
  // Fallback color when an edge has no tile sample. RGBA 0–1.
  float line[4] = {0.78f, 0.66f, 0.42f, 1.f};
  float scale = 1.f;
  bool smooth = true;
  bool blur = false;
};

struct SGlobalTextures {
  // Corners
  SP<ITexture> tl, tr, br, bl;
  // One fixed slice on each side of each corner (drawn once).
  // Top/bottom: left then right. Left/right edges: top then bottom.
  SP<ITexture> tfl, tfr, bfl, bfr, lft, lfb, rft, rfb;
  // Edge tile (repeated in the gaps) and the center graphic (drawn once).
  SP<ITexture> t, tc;
  SP<ITexture> r, rc;
  SP<ITexture> b, bc;
  SP<ITexture> l, lc;
  bool ready = false;
  bool failed = false;
};

struct SGlobalState {
  SImgBorderSettings settings;
  SGlobalTextures textures;
  uint32_t noImgBordersRuleIdx = 0;
};

extern UP<SGlobalState> g_pGlobalState;

void hyprframesLoadSettings(SImgBorderSettings &out);
void hyprframesEnsureTextures();
class CCompositor;

void hyprframesReload();
void hyprframesAttachExisting();
CCompositor *hyprframesCompositor();
