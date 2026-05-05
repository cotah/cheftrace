import { render, screen } from "@testing-library/react";
import HomePage from "../(marketing)/page";

test("landing page renders title", () => {
  render(<HomePage />);
  expect(screen.getByText("ChefTrace")).toBeInTheDocument();
});
