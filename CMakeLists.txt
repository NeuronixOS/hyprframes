cmake_minimum_required(VERSION 3.12)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(PkgConfig REQUIRED)

file(READ "${CMAKE_SOURCE_DIR}/VERSION" VERSION_RAW)
string(STRIP ${VERSION_RAW} VERSION)

project(
	hyprframes
	VERSION ${VERSION}
)

set(CMAKE_CXX_STANDARD 23)

add_compile_definitions(VERSION="${VERSION}")

# libhyprutils 0.14 made operator bool explicit. Hyprland 0.55.2 still
# converts those pointers implicitly, so build against the 0.13 headers.
# fetch-third-party.sh downloads them into third_party/ when missing.
execute_process(
	COMMAND "${CMAKE_SOURCE_DIR}/fetch-third-party.sh"
	WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
	RESULT_VARIABLE _hyprutils_fetch
)
if(NOT _hyprutils_fetch EQUAL 0)
	message(FATAL_ERROR "Failed to fetch third_party/hyprutils-0.13 headers (need network + curl/wget)")
endif()
include_directories(BEFORE "${CMAKE_SOURCE_DIR}/third_party/hyprutils-0.13")

include_directories(.)
add_library(hyprframes SHARED
	main.cpp
	Settings.cpp
	ImgBorder.cpp
	ImgBorderPassElement.cpp
	ImgUtils.cpp
)

pkg_check_modules(deps REQUIRED IMPORTED_TARGET
	hyprland
	libdrm
	pixman-1
	pangocairo
)
target_link_libraries(hyprframes PRIVATE rt PkgConfig::deps)

install(TARGETS hyprframes)
