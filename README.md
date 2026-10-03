# ImageBorders (Neuronix / Hyprland 0.55.2)

Tiling PNG borders around windows. Built and loaded for this machine only —
not via hyprpm/Nix.

## Files that matter

| Path | Role |
|------|------|
| `*.cpp` / `*.hpp` | Plugin source |
| `CMakeLists.txt` | Build |
| `example.png` | Demo 16×16 border texture |
| `imgborders.conf.example` | Copy → `~/.config/hypr/imgborders.conf` |
| `debug.sh` | Compile into `build/libimgborders.so` |
| `enable-next-login.sh` | Install `.so` + `plugin =` for next Hyprland start |
| `disable-imgborders.sh` | Undo that if login crashes |

`build/` is CMake output (object files + `libimgborders.so`). Safe to delete;
`./debug.sh` recreates it.

## Use

```bash
./debug.sh
./enable-next-login.sh   # only when Hyprland is not the session you need to keep
# log into Hyprland (new session). Do not hyprctl plugin load / reload.
```

Settings: `~/.config/hypr/imgborders.conf` (`image`, `sizes`, `insets`, `scale`, …).
Change image/settings → new Hyprland session (textures load once at start).
