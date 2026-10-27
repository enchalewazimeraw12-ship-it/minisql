"""Tkinter interface for running MiniSQL queries and viewing result tables."""
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, ttk

from minisql.compiler import compile_source, load_catalog
from minisql.errors import CompilerError
from minisql.executor import execute


ROOT = Path(__file__).resolve().parent


class MiniSQLApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MiniSQL Query Workbench")
        self.root.geometry("1000x720")
        self.catalog = load_catalog(str(ROOT / "data" / "sample_db.json"))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        header = ttk.Frame(root, padding=(16, 14, 16, 8))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="MiniSQL", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(header, text="Write a SELECT query and view its results below.").pack(anchor="w", pady=(3, 0))

        editor_frame = ttk.LabelFrame(root, text="SQL Query", padding=10)
        editor_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 10))
        editor_frame.columnconfigure(0, weight=1)
        self.editor = scrolledtext.ScrolledText(editor_frame, height=9, wrap="none", undo=True)
        self.editor.grid(row=0, column=0, sticky="ew")
        self.editor.insert(
            "1.0",
            "SELECT e.name, d.name AS department, e.salary * 12 AS yearly\n"
            "FROM employees e JOIN departments d ON e.dept_id = d.id\n"
            "WHERE d.city = 'Addis Ababa' AND e.age < 40\n"
            "ORDER BY yearly DESC LIMIT 3;",
        )
        self.editor.bind("<Control-Return>", self._run_shortcut)

        controls = ttk.Frame(editor_frame)
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(controls, text="Run Query", command=self.run_query).pack(side="left")
        ttk.Button(controls, text="Load Example", command=self.load_example).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Clear", command=self.clear_query).pack(side="left", padx=(8, 0))
        self.status = tk.StringVar(value="Ready")
        ttk.Label(controls, textvariable=self.status).pack(side="right")

        output_frame = ttk.LabelFrame(root, text="Query Output", padding=10)
        output_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)
        self.error_box = tk.Text(output_frame, height=4, wrap="word", state="disabled", foreground="#9b1c1c")
        self.error_box.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.tabs = ttk.Notebook(output_frame)
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self._show_message("Run a query to display its result here.")

    def _run_shortcut(self, _event):
        self.run_query()
        return "break"

    def _clear_output(self):
        for tab in self.tabs.tabs():
            self.tabs.forget(tab)
        self.error_box.configure(state="normal")
        self.error_box.delete("1.0", "end")
        self.error_box.configure(state="disabled")

    def _show_message(self, message):
        frame = ttk.Frame(self.tabs, padding=12)
        ttk.Label(frame, text=message).pack(anchor="w")
        self.tabs.add(frame, text="Output")

    def _show_errors(self, errors):
        self.error_box.configure(state="normal")
        self.error_box.delete("1.0", "end")
        self.error_box.insert("1.0", "\n".join(str(error) for error in errors))
        self.error_box.configure(state="disabled")

    @staticmethod
    def _display_value(value):
        if value is None:
            return "NULL"
        if isinstance(value, float):
            return f"{value:g}"
        return str(value)

    def _show_table(self, title, header, rows):
        frame = ttk.Frame(self.tabs, padding=6)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = [f"column_{index}" for index in range(len(header))]
        table = ttk.Treeview(frame, columns=columns, show="headings")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)

        for column, name in zip(columns, header):
            table.heading(column, text=name)
            table.column(column, width=max(110, min(240, len(name) * 12 + 24)), anchor="w")
        for row in rows:
            table.insert("", "end", values=[self._display_value(value) for value in row])

        table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tabs.add(frame, text=title)

    def run_query(self):
        source = self.editor.get("1.0", "end-1c").strip()
        self._clear_output()
        if not source:
            self.status.set("Enter a query first")
            self._show_message("The query editor is empty.")
            return

        result = compile_source(source, self.catalog)
        if result.errors:
            self._show_errors(result.errors)

        try:
            outputs = [execute(plan, self.catalog) for plan in result.plans]
        except CompilerError as error:
            self._show_errors(result.errors + [error])
            self.status.set("Query execution failed")
            self._show_message("The query could not be executed.")
            return

        if not outputs:
            if result.errors:
                self.status.set(f"Found {len(result.errors)} error(s)")
                self._show_message("No valid statements to run.")
            else:
                self.status.set("No statements to run")
                self._show_message("Enter one or more SELECT statements ending with semicolons.")
            return

        row_count = 0
        for index, (header, rows) in enumerate(outputs, start=1):
            self._show_table(f"Result {index}", header, rows)
            row_count += len(rows)
        status = f"Completed: {row_count} row(s) across {len(outputs)} statement(s)"
        if result.errors:
            status += f"; found {len(result.errors)} error(s)"
        self.status.set(status)

    def load_example(self):
        example = ROOT / "examples" / "valid.sql"
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", example.read_text(encoding="utf-8"))
        self.status.set("Loaded examples/valid.sql")

    def clear_query(self):
        self.editor.delete("1.0", "end")
        self._clear_output()
        self.status.set("Ready")
        self._show_message("Enter a query, then select Run Query.")


if __name__ == "__main__":
    window = tk.Tk()
    MiniSQLApp(window)
    window.mainloop()