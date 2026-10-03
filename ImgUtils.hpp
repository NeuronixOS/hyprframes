#pragma once

#include <hyprland/src/render/Texture.hpp>

using namespace Render;

namespace ImgUtils {
SP<ITexture> load(const std::string &filename);

SP<ITexture> sliceTexture(SP<ITexture> tex, CBox box);
} // namespace ImgUtils
