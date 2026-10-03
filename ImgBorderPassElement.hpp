#pragma once

#include <hyprland/src/render/Texture.hpp>
#include <hyprland/src/render/pass/PassElement.hpp>
#include <optional>

// Class defined elsewhere
class CImgBorder;

static const char *PASS_NAME = "CImgBorderPassElement";

class CImgBorderPassElement : public IPassElement {
public:
  struct SData {
    CImgBorder *deco = nullptr;
    float a = 1.F;
  };

  CImgBorderPassElement(const SData &data_);
  virtual ~CImgBorderPassElement();

  virtual std::vector<UP<IPassElement>> draw() override;
  virtual bool needsLiveBlur() override;
  virtual bool needsPrecomputeBlur() override;
  virtual const char *passName() override;
  virtual ePassElementType type() override;
  // virtual void discard() override;
  // virtual bool undiscardable() override;
  virtual std::optional<CBox> boundingBox() override;
  // virtual CRegion opaqueRegion() override;
  // virtual bool disableSimplification() override;

private:
  SData data;
};
