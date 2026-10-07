#pragma once

#include <cstdarg>
#include <string>

// Persistent debug log for post-crash forensics.
// Default: ~/.cache/hyprland/imgborders.log (flushed every line).
// Override with IMGBORDERS_LOG=/path/to/file.
namespace ImgLog {

void init();
const char *path();

void log(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
void stage(const char *name);     // breadcrumb + log line
void stageQuiet(const char *name); // breadcrumb only (hot path)

} // namespace ImgLog
