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
  box.width = std::max(1., box.width);
  box.height = std::max(1., box.height);

  SP<ITexture> tex = g_pHyprRenderer->createTexture();
  tex->allocate(box.size());

  const GLint glIFormat = GL_RGBA;
  const GLint glFormat = GL_RGBA;
  const GLint glType = GL_UNSIGNED_BYTE;
  const int DATA_SIZE = box.width * box.height * 4;
  const auto DATA = new unsigned char[DATA_SIZE]{0};
  glBindTexture(GL_TEXTURE_2D, tex->m_texID);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
  glTexImage2D(GL_TEXTURE_2D, 0, glIFormat, tex->m_size.x, tex->m_size.y, 0,
               glFormat, glType, DATA);
  delete[] DATA;

  glCopyImageSubData(src->m_texID, GL_TEXTURE_2D, 0, box.x, box.y, 0,
                     tex->m_texID, GL_TEXTURE_2D, 0, 0, 0, 0, tex->m_size.x,
                     tex->m_size.y, 1);

  return tex;
}
