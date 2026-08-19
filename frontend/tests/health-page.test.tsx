import { render, screen } from "@testing-library/react";
import HealthPage from "../app/health/page";

test("renders an available storefront status", () => {
  render(<HealthPage />);

  expect(screen.getByRole("heading", { name: "Storefront available" })).toBeInTheDocument();
});
