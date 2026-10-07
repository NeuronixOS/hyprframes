#include "ImgUtils.hpp"
#include <GLES3/gl32.h>
#include <cairo/cairo.h>
#include <filesystem>
#include <hyprland/src/debug/log/Logger.hpp>
#include <hyprland/src/helpers/Format.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/Texture.hpp>

using namespace Render;

SP<ITexture> createInvalidImageTexture() {
  const auto CAIROSURFACE =
      cairo_image_surface_create(CAIRO_FORMAT_ARGB32, 512, 512);
  const auto CAIRO = cairo_create(CAIROSURFACE);

  cairo_set_antialias(CAIRO, CAIRO_ANTIALIAS_NONE);
  cairo_save(CAIRO);
  cairo_set_source_rgba(CAIRO, 0, 0, 0, 1);
  cairo_set_operator(CAIRO, CAIRO_OPERATOR_SOURCE);
  cairo_paint(CAIRO);
  cairo_set_source_rgba(CAIRO, 1, 0, 1, 1);
  cairo_rectangle(CAIRO, 256, 0, 256, 256);
  cairo_fill(CAIRO);
  cairo_rectangle(CAIRO, 0, 256, 256, 256);
  cairo_fill(CAIRO);
  cairo_restore(CAIRO);
  cairo_surface_flush(CAIROSURFACE);

  auto tex = g_pHyprRenderer->createTexture(CAIROSURFACE);
  cairo_destroy(CAIRO);
  cairo_surface_destroy(CAIROSURFACE);
  return tex;
}

SP<ITexture> ImgUtils::load(const std::string &fullPath) {
  if (!std::filesystem::exists(fullPath)) {
    Log::logger->log(Log::ERR,
                     "ImgUtils failed to load {} (image doesn't exist. typo?)",
                     fullPath);
    return createInvalidImageTexture();
  }

  const auto CAIROSURFACE =
      cairo_image_surface_create_from_png(fullPath.c_str());
  if (!CAIROSURFACE ||
      cairo_surface_status(CAIROSURFACE) != CAIRO_STATUS_SUCCESS) {
    if (CAIROSURFACE)
      cairo_surface_destroy(CAIROSURFACE);
    Log::logger->log(
        Log::ERR,
        "ImgUtils failed to load {} (corrupt / inaccessible / not png)",
        fullPath);
    return createInvalidImageTexture();
  }

  auto tex = g_pHyprRenderer->createTexture(CAIROSURFACE);
  cairo_surface_destroy(CAIROSURFACE);
  return tex;
}

SP<ITexture> ImgUtils::sliceTexture(SP<ITexture> src, CBox box) {
  if (!src || src->m_texID == 0 || !g_pHyprRenderer)
    return nullptr;
  if (box.x < 0. || box.y < 0. || box.width < 1. || box.height < 1.)
    return nullptr;
  if (box.x + box.width > src->m_size.x + 0.5 ||
      box.y + box.height > src->m_size.y + 0.5)
    return nullptr;

  // Integer texel coords — drivers are unhappy with float truncation mismatch.
  const int sx = (int)box.x;
  const int sy = (int)box.y;
  const int sw = (int)box.width;
  const int sh = (int)box.height;
  if (sw < 1 || sh < 1)
    return nullptr;

  SP<ITexture> tex = g_pHyprRenderer->createTexture();
  if (!tex)
    return nullptr;
  tex->allocate({(double)sw, (double)sh});

  const GLint glIFormat = GL_RGBA;
  const GLint glFormat = GL_RGBA;
  const GLint glType = GL_UNSIGNED_BYTE;
  const size_t DATA_SIZE = (size_t)sw * (size_t)sh * 4;
  const auto DATA = new unsigned char[DATA_SIZE]{0};
  glBindTexture(GL_TEXTURE_2D, tex->m_texID);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
  // Cairo ARGB32 is BGRA in memory; createTexture(cairo) sets this swizzle.
  // glCopyImageSubData copies raw texels — without the same swizzle, R/B
  // swap and gold/amber borders render blue.
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_R, GL_BLUE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_SWIZZLE_B, GL_RED);
  glTexImage2D(GL_TEXTURE_2D, 0, glIFormat, sw, sh, 0, glFormat, glType, DATA);
  delete[] DATA;

  glCopyImageSubData(src->m_texID, GL_TEXTURE_2D, 0, sx, sy, 0, tex->m_texID,
                     GL_TEXTURE_2D, 0, 0, 0, 0, sw, sh, 1);

  return tex;
}
