import { expect, test } from "@playwright/test";
import { parseDecimal } from "../../lib/chartMath";

test("a Vietnamese keyboard decimal comma is understood; garbage is NaN", () => {
  expect(parseDecimal("4050,5")).toBe(4050.5);
  expect(parseDecimal("4050.5")).toBe(4050.5);
  expect(parseDecimal(" 4 050,25 ")).toBe(4050.25);
  expect(parseDecimal("4,050")).toBe(4050); // a thousands comma, not 4.05
  expect(parseDecimal("1,234,567")).toBe(1234567);
  expect(parseDecimal("0,25")).toBe(0.25);
  expect(Number.isNaN(parseDecimal(""))).toBe(true);
  expect(Number.isNaN(parseDecimal("abc"))).toBe(true);
});
