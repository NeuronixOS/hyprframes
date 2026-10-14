#include "ImgBorder.hpp"
#include "ImgBorderPassElement.hpp"
#include "globals.hpp"
#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/desktop/rule/windowRule/WindowRuleEffectContainer.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprutils/memory/UniquePtr.hpp>
#include <dlfcn.h>
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
  if (!PHANDLE || !g_pGlobalState || !window) {
    return;
  }
  if (!window->m_isMapped || window->isHidden() || window->m_X11DoesntWantBorders)
    return;
  if (alreadyDecorated(window))
    return;

  try {
    HyprlandAPI::addWindowDecoration(PHANDLE, window,
                                     makeUnique<CImgBorder>(window));
  } catch (...) {
  }
}

static void onWindowOpen(PHLWINDOW window) {
  if (!window || !g_pEventLoopManager)
    return;
  // Attach after mapWindow returns — never inside the map/rules stack.
  g_pEventLoopManager->doLater([window]() { addToWindow(window); });
}

static CCompositor *compositorFrom(void *sym) {
  if (!sym)
    return nullptr;
  auto *holder = static_cast<UP<CCompositor> *>(sym);
  return (holder && *holder) ? holder->get() : nullptr;
}

CCompositor *hyprframesCompositor() {
  // g_pCompositor is an inline unique symbol. A plugin loaded after startup
  // can see its own empty copy, so also look up the main executable's.
  CCompositor *compositor = g_pCompositor.get();
  CCompositor *fallback = compositorFrom(dlsym(RTLD_NEXT, "g_pCompositor"));
  if (!fallback)
    fallback = compositorFrom(dlsym(RTLD_DEFAULT, "g_pCompositor"));
  if (fallback &&
      (!compositor || fallback->m_windows.size() > compositor->m_windows.size()))
    compositor = fallback;
  return compositor;
}

void hyprframesAttachExisting() {
  CCompositor *compositor = hyprframesCompositor();
  if (!compositor)
    return;
  for (auto &w : compositor->m_windows) {
    if (!w || !w->m_isMapped || w->isHidden())
      continue;
    addToWindow(w);
  }
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
  PHANDLE = handle;

  const std::string COMPOSITOR_HASH = __hyprland_api_get_hash();
  const std::string CLIENT_HASH = __hyprland_api_get_client_hash();
  if (COMPOSITOR_HASH != CLIENT_HASH) {
    HyprlandAPI::addNotification(
        PHANDLE,
        "[hyprframes] Mismatched headers! Headers ver is not equal to running "
        "Hyprland ver.",
        CHyprColor{1.0, 0.2, 0.2, 1.0}, 5000);
    throw std::runtime_error("[hyprframes] Version mismatch");
  }

  g_pGlobalState = makeUnique<SGlobalState>();
  hyprframesLoadSettings(g_pGlobalState->settings);

  // No Hyprland addConfigValueV2 — those SPs die when hyprbars reloads config.
  g_pGlobalState->noImgBordersRuleIdx =
      Desktop::Rule::windowEffects()->registerEffect("hyprframes:nohyprframes");

  static auto windowOpenHook =
      Event::bus()->m_events.window.open.listen(onWindowOpen);

  HyprlandAPI::addDispatcherV2(PHANDLE, "hyprframesreload",
                               [](std::string) -> SDispatchResult {
                                 try {
                                   hyprframesReload();
                                   hyprframesAttachExisting();
                                 } catch (...) {
                                   return {.success = false,
                                           .error = "hyprframes reload failed"};
                                 }
                                 return {};
                               });

  hyprframesAttachExisting();

  return {"hyprframes", "Add image borders to windows.",
          "zacoons / Neuronix 0.55.2", VERSION};
}

APICALL EXPORT void PLUGIN_EXIT() {
  if (g_pHyprRenderer)
    g_pHyprRenderer->m_renderPass.removeAllOfType(PASS_NAME);

  if (g_pGlobalState)
    Desktop::Rule::windowEffects()->unregisterEffect(
        g_pGlobalState->noImgBordersRuleIdx);
}
