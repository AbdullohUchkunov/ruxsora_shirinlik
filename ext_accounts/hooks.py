app_name = "ext_accounts"
app_title = "ruxsora_app"
app_publisher = "abdulloh"
app_description = "for app ruxsora changing"
app_email = "abdullohuchkunov@gmail.com"
app_license = "mit"

# Fixtures
fixtures = [
    {"dt": "Custom Field", "filters": [["dt", "=", "Stock Entry"], ["fieldname", "=", "custom_production_entry"]]}
]

# Apps
# ------------------
app_include_js = [
    "/assets/ext_accounts/js/other_ext.js",
    "/assets/ext_accounts/js/purchase_invoice.js",
	"/assets/ext_accounts/js/purchase_receipt.js",
	"/assets/ext_accounts/js/sales_invoice.js",
	"/assets/ext_accounts/js/delivery_note.js",
	"/assets/ext_accounts/js/payment_entry.js"
]

# DocType overrides
override_doctype_class = {
    "Payment Entry": "ext_accounts.overrides.payment_entry_rashody.PaymentEntryRashody"
}

# DocType JS overrides
doctype_js = {
    "Payment Entry": "public/js/pe_override_full.js"
}

# Whitelisted method overrides
override_whitelisted_methods = {
    "erpnext.accounts.doctype.payment_entry.payment_entry.get_party_type":
        "ext_accounts.overrides.payment_entry_queries.get_party_type",
}
# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "ext_accounts",
# 		"logo": "/assets/ext_accounts/logo.png",
# 		"title": "ruxsora_app",
# 		"route": "/ext_accounts",
# 		"has_permission": "ext_accounts.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ext_accounts/css/ext_accounts.css"
# app_include_js = "/assets/ext_accounts/js/ext_accounts.js"

# include js, css files in header of web template
# web_include_css = "/assets/ext_accounts/css/ext_accounts.css"
# web_include_js = "/assets/ext_accounts/js/ext_accounts.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ext_accounts/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {
#     "Payment Entry": "public/js/pe_override_full.js"
# }
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "ext_accounts/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "ext_accounts.utils.jinja_methods",
# 	"filters": "ext_accounts.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "ext_accounts.install.before_install"
# after_install = "ext_accounts.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "ext_accounts.uninstall.before_uninstall"
# after_uninstall = "ext_accounts.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ext_accounts.utils.before_app_install"
# after_app_install = "ext_accounts.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ext_accounts.utils.before_app_uninstall"
# after_app_uninstall = "ext_accounts.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ext_accounts.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes
# override_doctype_class = {
#     "Payment Entry": "ext_accounts.overrides.payment_entry_rashody.PaymentEntryRashody"
# }

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Account": {
        "after_insert": "ext_accounts.overrides.account_hooks.after_insert",
        "on_update": "ext_accounts.overrides.account_hooks.on_update",
        "on_trash": "ext_accounts.overrides.account_hooks.on_trash"
    },
    	"Purchase Invoice": {
		"before_insert": "ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.apply_party_defaults",
		"before_validate": "ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.apply_party_defaults"
	},
	"Purchase Receipt": {
		"before_insert": "ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.apply_party_defaults",
		"before_validate": "ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.apply_party_defaults"
	},
	"Sales Invoice": {
		"before_insert": "ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.apply_party_defaults",
		"before_validate": "ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.apply_party_defaults"
	},
	"Delivery Note": {
		"before_insert": "ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.apply_party_defaults",
		"before_validate": "ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.apply_party_defaults"
	},
	"Payment Entry": {
		"before_insert": "ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.apply_party_defaults",
		"before_validate": "ext_accounts.ruxsora_app.doctype.party_financial_defaults.party_financial_defaults.apply_party_defaults"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"ext_accounts.tasks.all"
# 	],
# 	"daily": [
# 		"ext_accounts.tasks.daily"
# 	],
# 	"hourly": [
# 		"ext_accounts.tasks.hourly"
# 	],
# 	"weekly": [
# 		"ext_accounts.tasks.weekly"
# 	],
# 	"monthly": [
# 		"ext_accounts.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "ext_accounts.install.before_tests"

# Overriding Methods
# ------------------------------
override_whitelisted_methods = {
    "erpnext.accounts.doctype.payment_entry.payment_entry.get_party_type":
        "ext_accounts.overrides.payment_entry_queries.get_party_type",
}

# override_doctype_js = {
#     "erpnext.accounts.doctype.payment_entry.payment_entry": 
#         "public/js/disable_core_partytype.js"
# }
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ext_accounts.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ext_accounts.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ext_accounts.utils.before_request"]
# after_request = ["ext_accounts.utils.after_request"]

# Job Events
# ----------
# before_job = ["ext_accounts.utils.before_job"]
# after_job = ["ext_accounts.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"ext_accounts.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

