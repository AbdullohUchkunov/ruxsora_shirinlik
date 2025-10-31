from frappe import _

def get_data():
    return [
        {
            "label": _("Custom Reports"),
            "icon": "fa fa-file-text",
            "items": [
                {
                    "type": "report",
                    "is_query_report": True,
                    "name": "Akt Sverka",
                    "doctype": "GL Entry",
                    "label": _("Akt Sverka"),
                    "description": _("Qarzdorlik hisoboti bo‘yicha akt-sverka"),
                    "onboard": 1,
                }
            ]
        }
    ]
