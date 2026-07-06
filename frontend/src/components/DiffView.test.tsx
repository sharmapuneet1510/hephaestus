import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiffView } from "./DiffView";

const DIFF = `--- a/src/a.txt
+++ b/src/a.txt
@@ -1,3 +1,3 @@
 line 1
-line 2
+line TWO
 line 3
`;

describe("DiffView (SUBTASK 8.3)", () => {
  it("renders added and removed lines with distinct styling", () => {
    render(<DiffView diff={DIFF} />);
    expect(screen.getByText("+line TWO")).toHaveClass("diff-add");
    expect(screen.getByText("-line 2")).toHaveClass("diff-del");
    expect(screen.getByText("@@ -1,3 +1,3 @@")).toHaveClass("diff-hunk");
    // Context lines carry no add/remove class.
    expect(screen.getByText("line 1")).not.toHaveClass("diff-add");
  });
});
