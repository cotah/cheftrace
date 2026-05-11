import { render, screen } from "@testing-library/react";
import { ProducePreviewTable } from "../app/[restaurantId]/recipes/[id]/produce-dialog";
import type { RecipeProductionPreviewResponse } from "@/lib/api/types";

function build(
  overrides: Partial<RecipeProductionPreviewResponse> = {},
): RecipeProductionPreviewResponse {
  return {
    recipe_id: "00000000-0000-0000-0000-000000000001",
    batches: 1,
    can_confirm: true,
    lines: [],
    ...overrides,
  };
}

test("renders OK badge for a line with enough stock", () => {
  const preview = build({
    lines: [
      {
        ingredient_id: "ing-1",
        product_id: "prod-1",
        product_name: "Tomato",
        ingredient_unit: "kg",
        product_unit: "kg",
        quantity_needed: 2,
        available: 5,
        shortage: false,
        unit_mismatch: false,
        allocations: [
          {
            lot_id: "lot-1",
            expiry_date: "2026-05-15",
            quantity_from_lot: 2,
            unit_cost: 1.5,
            unit: "kg",
          },
        ],
      },
    ],
  });
  render(<ProducePreviewTable preview={preview} />);
  expect(screen.getByText("Tomato")).toBeInTheDocument();
  expect(screen.getByText("OK")).toBeInTheDocument();
  // Allocation line is rendered with lot info
  expect(screen.getByText(/expiry 2026-05-15/)).toBeInTheDocument();
});

test("renders Shortage badge when shortage is true", () => {
  const preview = build({
    can_confirm: false,
    lines: [
      {
        ingredient_id: "ing-1",
        product_id: "prod-1",
        product_name: "Tomato",
        ingredient_unit: "kg",
        product_unit: "kg",
        quantity_needed: 5,
        available: 1,
        shortage: true,
        unit_mismatch: false,
        allocations: [],
      },
    ],
  });
  render(<ProducePreviewTable preview={preview} />);
  expect(screen.getByText("Shortage")).toBeInTheDocument();
});

test("renders Unit mismatch badge and hides available", () => {
  const preview = build({
    can_confirm: false,
    lines: [
      {
        ingredient_id: "ing-1",
        product_id: "prod-1",
        product_name: "Salt",
        ingredient_unit: "kg",
        product_unit: "g",
        quantity_needed: 0.01,
        available: 0,
        shortage: false,
        unit_mismatch: true,
        allocations: [],
      },
    ],
  });
  render(<ProducePreviewTable preview={preview} />);
  expect(
    screen.getByText(/Unit mismatch \(kg vs g\)/),
  ).toBeInTheDocument();
  // The available cell shows a dash when unit_mismatch is true.
  expect(screen.getByText("—")).toBeInTheDocument();
});
