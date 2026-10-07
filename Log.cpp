#include "Log.hpp"
#include <chrono>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <fcntl.h>
#include <mutex>
#include <signal.h>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

namespace ImgLog {
namespace {

std::mutex g_mu;
std::string g_path;
bool g_ready = false;
char g_stage[256] = "uninitialized";
char g_pathBuf[512] = "/tmp/imgborders.log";

struct sigaction g_prevSegv {};
struct sigaction g_prevAbrt {};
struct sigaction g_prevBus {};
struct sigaction g_prevFpe {};
struct sigaction g_prevIll {};
bool g_hooksInstalled = false;

static void resolvePath() {
  if (const char *env = std::getenv("IMGBORDERS_LOG"); env && env[0]) {
    g_path = env;
  } else {
    const char *home = std::getenv("HOME");
    if (home && home[0])
      g_path = std::string(home) + "/.cache/hyprland/imgborders.log";
    else
      g_path = "/tmp/imgborders.log";
  }
  std::snprintf(g_pathBuf, sizeof(g_pathBuf), "%s", g_path.c_str());
}

static void ensureParentDir(const std::string &path) {
  auto slash = path.rfind('/');
  if (slash == std::string::npos || slash == 0)
    return;
  std::string dir = path.substr(0, slash);
  std::string cur;
  for (size_t i = 0; i < dir.size(); i++) {
    cur.push_back(dir[i]);
    if (dir[i] == '/' || i + 1 == dir.size()) {
      std::string d = cur;
      if (!d.empty() && d.back() == '/')
        d.pop_back();
      if (!d.empty() && d != "/")
        ::mkdir(d.c_str(), 0755);
    }
  }
}

static struct sigaction *prevFor(int sig) {
  switch (sig) {
  case SIGSEGV:
    return &g_prevSegv;
  case SIGABRT:
    return &g_prevAbrt;
  case SIGBUS:
    return &g_prevBus;
  case SIGFPE:
    return &g_prevFpe;
  case SIGILL:
    return &g_prevIll;
  default:
    return nullptr;
  }
}

static void chainPrev(int sig, siginfo_t *info, void *ctx) {
  struct sigaction *prev = prevFor(sig);
  if (!prev) {
    ::signal(sig, SIG_DFL);
    ::raise(sig);
    return;
  }
  if (prev->sa_flags & SA_SIGINFO) {
    if (prev->sa_sigaction)
      prev->sa_sigaction(sig, info, ctx);
    else {
      ::signal(sig, SIG_DFL);
      ::raise(sig);
    }
    return;
  }
  if (prev->sa_handler == SIG_IGN)
    return;
  if (prev->sa_handler == SIG_DFL || !prev->sa_handler) {
    ::signal(sig, SIG_DFL);
    ::raise(sig);
    return;
  }
  prev->sa_handler(sig);
}

// Async-signal-safe crash note, then chain to Hyprland's reporter.
static void crashHandler(int sig, siginfo_t *info, void *ctx) {
  int fd = ::open(g_pathBuf, O_WRONLY | O_APPEND | O_CREAT, 0644);
  if (fd >= 0) {
    char buf[640];
    int n = std::snprintf(
        buf, sizeof(buf),
        "\n*** IMGBORDERS CRASH signal=%d stage=%s pid=%d\n", sig, g_stage,
        (int)::getpid());
    if (n > 0) {
      size_t len = (size_t)n;
      if (len >= sizeof(buf))
        len = sizeof(buf) - 1;
      (void)::write(fd, buf, len);
    }
    (void)::fsync(fd);
    ::close(fd);
  }
  chainPrev(sig, info, ctx);
}

static void installOne(int sig, struct sigaction *save) {
  struct sigaction sa {};
  sa.sa_sigaction = crashHandler;
  sigemptyset(&sa.sa_mask);
  sa.sa_flags = SA_SIGINFO;
  ::sigaction(sig, &sa, save);
}

static void installCrashHooks() {
  if (g_hooksInstalled)
    return;
  installOne(SIGSEGV, &g_prevSegv);
  installOne(SIGABRT, &g_prevAbrt);
  installOne(SIGBUS, &g_prevBus);
  installOne(SIGFPE, &g_prevFpe);
  installOne(SIGILL, &g_prevIll);
  g_hooksInstalled = true;
}

} // namespace

void init() {
  std::lock_guard<std::mutex> lock(g_mu);
  resolvePath();
  ensureParentDir(g_path);
  g_ready = true;
  std::snprintf(g_stage, sizeof(g_stage), "%s", "init");
  installCrashHooks();

  FILE *f = std::fopen(g_path.c_str(), "a");
  if (!f)
    return;
  const auto now = std::chrono::system_clock::now();
  const std::time_t t = std::chrono::system_clock::to_time_t(now);
  char tbuf[64];
  std::strftime(tbuf, sizeof(tbuf), "%Y-%m-%d %H:%M:%S", std::localtime(&t));
  std::fprintf(f,
               "\n======== imgborders session start %s pid=%d ========\n"
               "log=%s\n",
               tbuf, (int)::getpid(), g_path.c_str());
  std::fflush(f);
  std::fclose(f);
}

const char *path() {
  if (g_path.empty())
    resolvePath();
  return g_path.c_str();
}

void stageQuiet(const char *name) {
  if (!name)
    name = "?";
  std::snprintf(g_stage, sizeof(g_stage), "%s", name);
}

void stage(const char *name) {
  stageQuiet(name);
  log("STAGE %s", name ? name : "?");
}

void log(const char *fmt, ...) {
  if (!g_ready) {
    resolvePath();
    ensureParentDir(g_path);
    g_ready = true;
  }

  char msg[1024];
  va_list ap;
  va_start(ap, fmt);
  std::vsnprintf(msg, sizeof(msg), fmt, ap);
  va_end(ap);

  const auto now = std::chrono::system_clock::now();
  const std::time_t t = std::chrono::system_clock::to_time_t(now);
  char tbuf[32];
  std::strftime(tbuf, sizeof(tbuf), "%H:%M:%S", std::localtime(&t));

  std::lock_guard<std::mutex> lock(g_mu);
  FILE *f = std::fopen(g_path.c_str(), "a");
  if (!f)
    return;
  std::fprintf(f, "[%s] %s\n", tbuf, msg);
  std::fflush(f);
  std::fclose(f);
}

} // namespace ImgLog
