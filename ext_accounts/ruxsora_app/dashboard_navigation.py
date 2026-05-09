from __future__ import annotations

import frappe


DEFAULT_DASHBOARD_LINKS = [
    {"label": "Main dashboard", "route": "main-dashboard"},
    {"label": "Page dashboard", "route": "page-dashboard"},
    {"label": "Sales dashboard", "route": "sales-dashboard"},
    {"label": "Daily dashboard", "route": "daily-dashboard"},
    {"label": "Supplier dashboard", "route": "supplier-dashboard"},
]


@frappe.whitelist()
def get_dashboard_links() -> list[dict[str, str]]:
    rows = frappe.get_all(
        "Workspace Link",
        filters={
            "parent": "Dashboards",
            "type": "Link",
            "link_type": "Page",
            "hidden": 0,
        },
        fields=["label", "link_to"],
        order_by="idx asc",
    )

    links = [
        {"label": row.label, "route": row.link_to}
        for row in rows
        if row.label and row.link_to
    ]

    return links or DEFAULT_DASHBOARD_LINKS
