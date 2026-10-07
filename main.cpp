#include "ImgBorder.hpp"
#include "ImgBorderPassElement.hpp"
#include "Log.hpp"
#include "globals.hpp"
#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/desktop/rule/windowRule/WindowRuleEffectContainer.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprutils/memory/UniquePtr.hpp>
#include <exception>

APICALL EXPORT std::string PLUGIN_API_VERSION() { return HYPRLAND_API_VERSION; }

static bool alreadyDecorated(PHLWINDOW window) {
  if (!window)
    return true;
  for (const auto &d : window->m_windowDecorations) {
    if (d && d->getDisplayName() == DISPLAY_NAME)
      return true;
  }
  return false;
}

static void addToWindow(PHLWINDOW window) {
  ImgLog::stage("addToWindow");
  if (!PHANDLE || !g_pGlobalState || !window) {
    ImgLog::log("addToWindow skip: null handle/state/window");
    return;
  }
  if (!window->m_isMapped || window->isHidden() || window->m_X11DoesntWantBorders)
    return;
  if (alreadyDecorated(window))
    return;

  try {
    ImgLog::log("addWindowDecoration class=%s",
                window->m_class.empty() ? "?" : window->m_class.c_str());
    HyprlandAPI::addWindowDecoration(PHANDLE, window,
                                     makeUnique<CImgBorder>(window));
    ImgLog::stage("addToWindow.done");
  } catch (const std::exception &e) {
    ImgLog::log("ERROR addToWindow exception: %s", e.what());
  } catch (...) {
    ImgLog::log("ERROR addToWindow unknown exception");
  }
}

static void onWindowOpen(PHLWINDOW window) {
  if (!window || !g_pEventLoopManager)
    return;
  ImgLog::log("window.open scheduled (doLater)");
  // Attach after mapWindow returns — never inside the map/rules stack.
  g_pEventLoopManager->doLater([window]() { addToWindow(window); });
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
  ImgLog::init();
  ImgLog::stage("PLUGIN_INIT");
  PHANDLE = handle;

  const std::string COMPOSITOR_HASH = __hyprland_api_get_hash();
  const std::string CLIENT_HASH = __hyprland_api_get_client_hash();
  ImgLog::log("hashes compositor=%s client=%s match=%d",
              COMPOSITOR_HASH.c_str(), CLIENT_HASH.c_str(),
              COMPOSITOR_HASH == CLIENT_HASH ? 1 : 0);
  if (COMPOSITOR_HASH != CLIENT_HASH) {
    ImgLog::log("ERROR version mismatch — refusing init");
    HyprlandAPI::addNotification(
        PHANDLE,
        "[imgborders] Mismatched headers! Headers ver is not equal to running "
        "Hyprland ver.",
        CHyprColor{1.0, 0.2, 0.2, 1.0}, 5000);
    throw std::runtime_error("[imgborders] Version mismatch");
  }

  g_pGlobalState = makeUnique<SGlobalState>();
  ImgLog::stage("loadSettings");
  imgbordersLoadSettings(g_pGlobalState->settings);
  ImgLog::log("settings image=%s sizes=%d,%d,%d,%d centers=%d,%d,%d,%d "
              "scale=%.2f smooth=%d blur=%d",
              g_pGlobalState->settings.imagePath,
              g_pGlobalState->settings.sizes[0],
              g_pGlobalState->settings.sizes[1],
              g_pGlobalState->settings.sizes[2],
              g_pGlobalState->settings.sizes[3],
              g_pGlobalState->settings.centers[0],
              g_pGlobalState->settings.centers[1],
              g_pGlobalState->settings.centers[2],
              g_pGlobalState->settings.centers[3],
              g_pGlobalState->settings.scale,
              g_pGlobalState->settings.smooth ? 1 : 0,
              g_pGlobalState->settings.blur ? 1 : 0);

  // No Hyprland addConfigValueV2 — those SPs die when hyprbars reloads config.
  ImgLog::stage("registerEffect");
  g_pGlobalState->noImgBordersRuleIdx =
      Desktop::Rule::windowEffects()->registerEffect("imgborders:noimgborders");

  ImgLog::stage("listen.window.open");
  static auto windowOpenHook =
      Event::bus()->m_events.window.open.listen(onWindowOpen);

  HyprlandAPI::addDispatcherV2(PHANDLE, "imgbordersreload",
                               [](std::string) -> SDispatchResult {
                                 ImgLog::stage("dispatcher.imgbordersreload");
                                 try {
                                   imgbordersReload();
                                   ImgLog::log("reload ok");
                                 } catch (const std::exception &e) {
                                   ImgLog::log("ERROR reload: %s", e.what());
                                   return {.success = false,
                                           .error = "imgborders reload failed"};
                                 } catch (...) {
                                   ImgLog::log("ERROR reload unknown");
                                   return {.success = false,
                                           .error = "imgborders reload failed"};
                                 }
                                 return {};
                               });

  ImgLog::stage("PLUGIN_INIT.done");
  ImgLog::log("plugin ready; crash breadcrumbs → %s", ImgLog::path());
  return {"imgborders", "Add image borders to windows.",
          "zacoons / Neuronix 0.55.2", VERSION};
}

APICALL EXPORT void PLUGIN_EXIT() {
  ImgLog::stage("PLUGIN_EXIT");
  if (g_pHyprRenderer)
    g_pHyprRenderer->m_renderPass.removeAllOfType(PASS_NAME);

  if (g_pGlobalState)
    Desktop::Rule::windowEffects()->unregisterEffect(
        g_pGlobalState->noImgBordersRuleIdx);
  ImgLog::log("PLUGIN_EXIT complete");
}
