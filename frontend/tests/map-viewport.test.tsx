import { render } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

const mocks = vi.hoisted(() => ({ setView: vi.fn() }));
vi.mock("react-leaflet", () => ({ useMap: () => ({ setView: mocks.setView }) }));

import { MapRecenter } from "@/components/account/address-map-inner";

describe("MapRecenter", () => {
  test("recenters Leaflet when selected or keyboard-edited coordinates change", () => {
    const { rerender } = render(<MapRecenter latitude={-34.6037} longitude={-58.3816} />);
    expect(mocks.setView).toHaveBeenLastCalledWith([-34.6037, -58.3816], 17, { animate: false });
    rerender(<MapRecenter latitude={-34.62} longitude={-58.39} />);
    expect(mocks.setView).toHaveBeenLastCalledWith([-34.62, -58.39], 17, { animate: false });
    expect(mocks.setView).toHaveBeenCalledTimes(2);
  });
});
