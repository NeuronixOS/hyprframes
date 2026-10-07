#include "globals.hpp"
#include "ImgBorder.hpp"
#include "ImgUtils.hpp"
#include "Log.hpp"
#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

UP<SGlobalState> g_pGlobalState;

static std::string trim(std::string s) {
  while (!s.empty() && (s.front() == ' ' || s.front() == '\t'))
    s.erase(s.begin());
  while (!s.empty() &&
         (s.back() == ' ' || s.back() == '\t' || s.back() == '\r'))
    s.pop_back();
  return s;
}

static void parseGaps(const std::string &v, int out[4]) {
  std::stringstream ss(v);
  std::string part;
  int vals[4] = {out[0], out[1], out[2], out[3]};
  int n = 0;
  while (std::getline(ss, part, ',') && n < 4) {
    part = trim(part);
    if (part.empty())
      continue;
    vals[n++] = std::stoi(part);
  }
  if (n == 1) {
    out[0] = out[1] = out[2] = out[3] = vals[0];
  } else if (n == 4) {
    out[0] = vals[0];
    out[1] = vals[1];
    out[2] = vals[2];
    out[3] = vals[3];
  }
}

static void loadFile(const std::string &path, SImgBorderSettings &out) {
  std::ifstream in(path);
  if (!in)
    return;

  std::string line;
  while (std::getline(in, line)) {
    line = trim(line);
    if (line.empty() || line[0] == '#' || line[0] == ';')
      continue;
    const auto eq = line.find('=');
    if (eq == std::string::npos)
      continue;
    const auto key = trim(line.substr(0, eq));
    auto val = trim(line.substr(eq + 1));
    if (!val.empty() &&
        ((val.front() == '"' && val.back() == '"') ||
         (val.front() == '\'' && val.back() == '\'')))
      val = val.substr(1, val.size() - 2);

    try {
      if (key == "image") {
        std::snprintf(out.imagePath, sizeof(out.imagePath), "%s", val.c_str());
      } else if (key == "sizes")
        parseGaps(val, out.sizes);
      else if (key == "insets")
        parseGaps(val, out.insets);
      else if (key == "centers")
        parseGaps(val, out.centers);
      else if (key == "flanks")
        parseGaps(val, out.flanks);
      else if (key == "scale")
        out.scale = std::stof(val);
      else if (key == "smooth")
        out.smooth = !(val == "0" || val == "false" || val == "no");
      else if (key == "blur")
        out.blur = (val == "1" || val == "true" || val == "yes");
    } catch (...) {
    }
  }
}

void imgbordersLoadSettings(SImgBorderSettings &out) {
  loadFile("/usr/share/neuronix/imgborders/imgborders.conf", out);
  const char *home = std::getenv("HOME");
  if (home)
    loadFile(std::string(home) + "/.config/hypr/imgborders.conf", out);
}

void imgbordersEnsureTextures() {
  if (!g_pGlobalState)
    return;
  auto &tex = g_pGlobalState->textures;
  if (tex.ready || tex.failed)
    return;

  ImgLog::stage("ensureTextures");
  auto &s = g_pGlobalState->settings;
  if (s.imagePath[0] == '\0' || !std::filesystem::exists(s.imagePath)) {
    const char *home = std::getenv("HOME");
    const char *fallbacks[3] = {
        "/usr/share/neuronix/imgborders/example.png",
        nullptr,
        nullptr,
    };
    static char localShare[512];
    if (home) {
      std::snprintf(localShare, sizeof(localShare),
                    "%s/.local/share/neuronix/imgborders/example.png", home);
      fallbacks[1] = localShare;
    }
    for (const char *fb : fallbacks) {
      if (fb && std::filesystem::exists(fb)) {
        std::snprintf(s.imagePath, sizeof(s.imagePath), "%s", fb);
        break;
      }
    }
  }
  if (s.imagePath[0] == '\0' || !std::filesystem::exists(s.imagePath)) {
    ImgLog::log("ERROR no image path / missing file");
    tex.failed = true;
    return;
  }

  for (int i = 0; i < 4; i++) {
    if (s.sizes[i] < 0 || s.centers[i] < 0 || s.flanks[i] < 0) {
      ImgLog::log("ERROR negative sizes/centers/flanks");
      tex.failed = true;
      return;
    }
  }

  ImgLog::log("loading %s", s.imagePath);
  ImgLog::stage("loadPNG");
  auto src = ImgUtils::load(s.imagePath);
  if (!src) {
    ImgLog::log("ERROR ImgUtils::load returned null");
    tex.failed = true;
    return;
  }
  ImgLog::log("png size=%.0fx%.0f", src->m_size.x, src->m_size.y);

  const float L = (float)s.sizes[0];
  const float R = (float)s.sizes[1];
  const float T = (float)s.sizes[2];
  const float B = (float)s.sizes[3];
  const float WM = src->m_size.x - L - R;
  const float HM = src->m_size.y - T - B;
  if (WM <= 0 || HM <= 0) {
    ImgLog::log("ERROR mid strip invalid WM=%.1f HM=%.1f (sizes too large?)",
                WM, HM);
    tex.failed = true;
    return;
  }

  // Mid strip: [FLANK][TILE][CENTER][FLANK]. flanks=0 keeps the 13-patch.
  struct Split {
    float flankA, tile, center, flankB;
  };
  auto split = [](float mid, int centerWant, int flankWant) -> Split {
    float flank = std::clamp((float)flankWant, 0.f, mid * 0.5f);
    float center = std::clamp((float)centerWant, 0.f, mid - 2.f * flank);
    float tile = mid - 2.f * flank - center;
    if (tile < 0.f)
      tile = 0.f;
    return {flank, tile, center, flank};
  };

  const auto top = split(WM, s.centers[0], s.flanks[0]);
  const auto right = split(HM, s.centers[1], s.flanks[1]);
  const auto bottom = split(WM, s.centers[2], s.flanks[2]);
  const auto left = split(HM, s.centers[3], s.flanks[3]);
  const float Wt = top.tile, Wc = top.center, FtL = top.flankA, FtR = top.flankB;
  const float HbR = right.tile, HcR = right.center, FrT = right.flankA, FrB = right.flankB;
  const float Wb = bottom.tile, Bc = bottom.center, FbL = bottom.flankA, FbR = bottom.flankB;
  const float Ht = left.tile, HcL = left.center, FlT = left.flankA, FlB = left.flankB;
  ImgLog::log("21-patch mid=%.0fx%.0f flank/tile/center T=%.0f/%.0f/%.0f "
              "R=%.0f/%.0f/%.0f B=%.0f/%.0f/%.0f L=%.0f/%.0f/%.0f",
              WM, HM, FtL, Wt, Wc, FrT, HbR, HcR, FbL, Wb, Bc, FlT, Ht, HcL);

  ImgLog::stage("slice.corners");
  tex.tl = ImgUtils::sliceTexture(src, {{0., 0.}, {L, T}});
  tex.tr = ImgUtils::sliceTexture(src, {{src->m_size.x - R, 0.}, {R, T}});
  tex.br = ImgUtils::sliceTexture(
      src, {{src->m_size.x - R, src->m_size.y - B}, {R, B}});
  tex.bl = ImgUtils::sliceTexture(src, {{0., src->m_size.y - B}, {L, B}});

  ImgLog::stage("slice.edges");
  auto sliceOrNull = [&](float x, float y, float w, float h) -> SP<ITexture> {
    if (w <= 0.f || h <= 0.f)
      return nullptr;
    return ImgUtils::sliceTexture(src, {{x, y}, {w, h}});
  };

  // Top: [flank by TL][tile][center][flank by TR]
  tex.tfl = sliceOrNull(L, 0., FtL, T);
  tex.t = sliceOrNull(L + FtL, 0., Wt, T);
  tex.tc = sliceOrNull(L + FtL + Wt, 0., Wc, T);
  tex.tfr = sliceOrNull(L + FtL + Wt + Wc, 0., FtR, T);

  // Bottom
  const float by = src->m_size.y - B;
  tex.bfl = sliceOrNull(L, by, FbL, B);
  tex.b = sliceOrNull(L + FbL, by, Wb, B);
  tex.bc = sliceOrNull(L + FbL + Wb, by, Bc, B);
  tex.bfr = sliceOrNull(L + FbL + Wb + Bc, by, FbR, B);

  // Left: [flank by TL][tile][center][flank by BL]
  tex.lft = sliceOrNull(0., T, L, FlT);
  tex.l = sliceOrNull(0., T + FlT, L, Ht);
  tex.lc = sliceOrNull(0., T + FlT + Ht, L, HcL);
  tex.lfb = sliceOrNull(0., T + FlT + Ht + HcL, L, FlB);

  // Right
  const float rx = src->m_size.x - R;
  tex.rft = sliceOrNull(rx, T, R, FrT);
  tex.r = sliceOrNull(rx, T + FrT, R, HbR);
  tex.rc = sliceOrNull(rx, T + FrT + HbR, R, HcR);
  tex.rfb = sliceOrNull(rx, T + FrT + HbR + HcR, R, FrB);

  tex.ready = true;
  ImgLog::stage("ensureTextures.done");
  ImgLog::log("textures ready tl=%d tr=%d br=%d bl=%d t=%d tc=%d r=%d rc=%d "
              "b=%d bc=%d l=%d lc=%d",
              tex.tl ? 1 : 0, tex.tr ? 1 : 0, tex.br ? 1 : 0, tex.bl ? 1 : 0,
              tex.t ? 1 : 0, tex.tc ? 1 : 0, tex.r ? 1 : 0, tex.rc ? 1 : 0,
              tex.b ? 1 : 0, tex.bc ? 1 : 0, tex.l ? 1 : 0, tex.lc ? 1 : 0);
}

static void clearTextures(SGlobalTextures &tex) {
  tex.ready = false;
  tex.failed = false;
  tex.tl = tex.tr = tex.br = tex.bl = nullptr;
  tex.tfl = tex.tfr = tex.bfl = tex.bfr = nullptr;
  tex.lft = tex.lfb = tex.rft = tex.rfb = nullptr;
  tex.t = tex.tc = nullptr;
  tex.r = tex.rc = nullptr;
  tex.b = tex.bc = nullptr;
  tex.l = tex.lc = nullptr;
}

void imgbordersReload() {
  if (!g_pGlobalState)
    return;

  ImgLog::stage("reload");
  clearTextures(g_pGlobalState->textures);

  g_pGlobalState->settings = SImgBorderSettings{};
  imgbordersLoadSettings(g_pGlobalState->settings);
  ImgLog::log("reload image=%s centers=%d,%d,%d,%d",
              g_pGlobalState->settings.imagePath,
              g_pGlobalState->settings.centers[0],
              g_pGlobalState->settings.centers[1],
              g_pGlobalState->settings.centers[2],
              g_pGlobalState->settings.centers[3]);

  try {
    imgbordersEnsureTextures();
  } catch (const std::exception &e) {
    ImgLog::log("ERROR ensureTextures: %s", e.what());
    g_pGlobalState->textures.failed = true;
    return;
  } catch (...) {
    ImgLog::log("ERROR ensureTextures unknown");
    g_pGlobalState->textures.failed = true;
    return;
  }

  if (!g_pCompositor || !g_pGlobalState->textures.ready) {
    ImgLog::log("reload: textures not ready (failed=%d)",
                g_pGlobalState->textures.failed ? 1 : 0);
    return;
  }

  if (!g_pEventLoopManager)
    return;
  ImgLog::stage("reload.applyLater");
  g_pEventLoopManager->doLater([]() {
    ImgLog::stage("reload.apply");
    if (!g_pCompositor || !g_pGlobalState)
      return;
    int n = 0;
    try {
      for (auto &w : g_pCompositor->m_windows) {
        if (!w || !w->m_isMapped || w->isHidden())
          continue;
        for (auto &d : w->m_windowDecorations) {
          if (!d || d->getDisplayName() != DISPLAY_NAME)
            continue;
          static_cast<CImgBorder *>(d.get())->applySettings();
          n++;
        }
      }
    } catch (const std::exception &e) {
      ImgLog::log("ERROR reload.apply: %s", e.what());
    } catch (...) {
      ImgLog::log("ERROR reload.apply unknown");
    }
    ImgLog::log("reload applied to %d decorations", n);
    ImgLog::stage("idle");
  });
}
