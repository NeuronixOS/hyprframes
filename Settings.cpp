#include "globals.hpp"
#include "ImgUtils.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
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

void imgbordersLoadSettings(SImgBorderSettings &out) {
  const char *home = std::getenv("HOME");
  if (!home)
    return;

  const std::string path =
      std::string(home) + "/.config/hypr/imgborders.conf";
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

void imgbordersEnsureTextures() {
  if (!g_pGlobalState)
    return;
  auto &tex = g_pGlobalState->textures;
  if (tex.ready || tex.failed)
    return;

  const auto &s = g_pGlobalState->settings;
  if (s.imagePath[0] == '\0' || !std::filesystem::exists(s.imagePath)) {
    tex.failed = true;
    return;
  }

  for (int i = 0; i < 4; i++) {
    if (s.sizes[i] < 0) {
      tex.failed = true;
      return;
    }
  }

  auto src = ImgUtils::load(s.imagePath);
  if (!src) {
    tex.failed = true;
    return;
  }

  const float L = (float)s.sizes[0];
  const float R = (float)s.sizes[1];
  const float T = (float)s.sizes[2];
  const float B = (float)s.sizes[3];
  const float WM = src->m_size.x - L - R;
  const float HM = src->m_size.y - T - B;
  if (WM <= 0 || HM <= 0) {
    tex.failed = true;
    return;
  }

  tex.tl = ImgUtils::sliceTexture(src, {{0., 0.}, {L, T}});
  tex.t = ImgUtils::sliceTexture(src, {{L, 0.}, {WM, T}});
  tex.tr = ImgUtils::sliceTexture(src, {{src->m_size.x - R, 0.}, {R, T}});
  tex.r = ImgUtils::sliceTexture(src, {{src->m_size.x - R, T}, {R, HM}});
  tex.br =
      ImgUtils::sliceTexture(src, {{src->m_size.x - R, src->m_size.y - B}, {R, B}});
  tex.b = ImgUtils::sliceTexture(src, {{L, src->m_size.y - B}, {WM, B}});
  tex.bl = ImgUtils::sliceTexture(src, {{0., src->m_size.y - B}, {L, B}});
  tex.l = ImgUtils::sliceTexture(src, {{0., T}, {L, HM}});
  tex.ready = true;
}
