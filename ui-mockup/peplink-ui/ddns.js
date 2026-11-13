if (!window.Help) { Help = {}; }
Help["ddns.info"] = $.i18n("help-ddns.info",
"<a href=\"#\" data-handler=\"show_ddns_ip_detection_options\">",
"</a>",
"<a href=\"http://www.dnsomatic.com/\" target=\"_blank\">",
"</a>",
(window.comname));

(function(root) {

	var	$ = root.jQuery,
		_console = /* root.console || */ { log: $.noop },
		_ddm = [
			[ "disable", $.i18n("Disabled") ],
			[ "changeip", "changeip.com" ],
			[ "dyndns", "dyndns.org" ],
			[ "noip", "no-ip.org" ],
			[ "dnsomatic", "DNS-O-Matic" ],
			[ "others", $.i18n("ddns-others") ]
		],
		_ddn = {
			changeip: {
				ddns_username: $.i18n("ddns-userId")
			},
			noip: {
				ddns_username: $.i18n("Email")
			},
			dnsomatic: {
				ddns_host: $.i18n("ddns-hostId")
			},
			def: {
				ddns_others_url: "URL",
				ddns_username: $.i18n("Username"),
				ddns_password: $.i18n("Password"),
				ddns_password2: $.i18n("Confirm Password"),
				ddns_host: $.i18n("ddns-hosts")
			}
		},
		_ddd = {
			disable:	[ "ddns_main_panel" ],
			changeip:	[ "ddns_main_panel", "ddns_default_panel", "ddns_host_panel" ],
			dyndns:		[ "ddns_main_panel", "ddns_default_panel", "ddns_host_panel" ],
			noip:		[ "ddns_main_panel", "ddns_default_panel", "ddns_host_panel" ],
			dnsomatic:	[ "ddns_main_panel", "ddns_default_panel", "ddns_matic_panel", "ddns_host_panel" ],
			others:		[ "ddns_main_panel", "ddns_server_panel", "ddns_default_panel", "ddns_host_panel" ]
		},
		_ddv = {
			provider:	"disable",
			username:	"",
			password:	"",
			host:		[]
		},
// {{{ Internal Utility Functions - _get_field_name, _get_panel, _get_panel_filter, _get_option
		_get_field_name = function(m) { return $.extend({}, _ddn["def"], _ddn[m] || {}); },
		_get_panel = function(m) { return _ddd[m] || _ddd["disable"]; },
		_get_panel_filter = function(m) { return $.map(_get_panel(m), function(o) { return "."+o; }).join(", "); },
		_get_option = function(l) { return $.map(l, function(o) { return $("<option/>").val(o[0]).text(o[1]); }); },
// }}}
// {{{ Internal Functions - _create_ddns_rows()
		_create_ddns_rows = function() {
			var	std_css = { width: "200px" },
				std_attr = { maxlength: "50" },
				dn = _get_field_name("def"),
				rows = [
					create_form_row($.i18n("ddns-serviceProvide"), [
						$("<select/>", { name: "ddns_provider" }).css(std_css).addClass("ddns_action").append(_get_option(_ddm)),
						$("<span/>").append(
							" URL: ",
							$("<input/>", {
								name: "ddns_others_url",
								placeholder: "members.dyndns.org/nic/update"
							}).css({ width: "220px" })
						).addClass("ddns_panel ddns_server_panel")
					], "ddns.info").addClass("ddns_main_panel"),
					create_form_row($.i18n("IP Address"), create_radio_input("ddns_ipaddr", {
						"": $.i18n("ddns-detectAuto"),
						"local": $.i18n("ddns-announceWanIp")
					})).addClass("ddns_detection_options").hide(),
					create_form_row(dn["ddns_username"],
						$("<input/>", $.extend({ name: "ddns_username" }, std_attr)).css(std_css)
					).addClass("ddns_default_panel"),
					create_form_row(dn["ddns_password"],
						$("<input/>", $.extend({ name: "ddns_password", type: "password" }, std_attr)).css(std_css)
					).addClass("ddns_default_panel"),
					create_form_row(dn["ddns_password2"],
						$("<input/>", $.extend({ name: "ddns_password2", type: "password" }, std_attr)).css(std_css)
					).addClass("ddns_default_panel"),
					create_form_row($.i18n("ddns-updateAllHosts"),
						$("<input/>", { name: "ddns_update_all_host", type: "checkbox" }).prop("checked", true).addClass("ddns_update_all")
					).addClass("ddns_matic_panel"),
					create_form_row(dn["ddns_host"],
						$("<textarea/>", { name: "ddns_host" }).css($.extend({ height: "90px" }, std_css))
					).addClass("ddns_host_panel")
				];
			$.each(rows, function() { this.addClass("ddns_panel"); });
			return rows;
		},
// }}}
// {{{ Internal Methods - _redraw_method, _set_method
		_redraw_method = function(e) {
_console.log("redraw.ddns_panel")
			var	me = $(this),
				provider = me.find("select").filter("[name=ddns_provider]").val(),
				fields_all = me.find("input, textarea"),
				rows_all = me.find(".ddns_panel"),
				rows_show = rows_all.filter(_get_panel_filter(provider)),
				is_update_all = me.find("input[name=\"ddns_update_all_host\"]").prop("checked");
			$.each(_get_field_name(provider), function(i, v) {
				fields_all.filter("[name=\"" + i + "\"]")
				.closest(".ddns_panel").find("td").first()
				.text(v);
			});
			rows_all.not(rows_show.show()).hide();
			rows_all.filter(".ddns_detection_options").toggle(!!me.data("show_detection"));
			if (provider=="dnsomatic")
				rows_show.filter(".ddns_host_panel").toggle(!is_update_all);
			me.triggerHandler("_callback");
		},
		_set_method = function(e, _info) {
			var	me = $(this),
				info = $.extend({}, _ddv, $.isPlainObject(_info) ? _info : {}),
				is_local_ipaddr = info["useWanIp"];
			// {{{ TO_BE_REMOVED: In order not to break the old wan page
			if (is_local_ipaddr === undefined) {
				is_local_ipaddr = !!(info["ipaddr"] == "local");
			}
			// }}}
			me.data("show_detection", is_local_ipaddr);
			me.find("select").filter("[name=ddns_provider]")
			.data("prev", info["provider"])
			.find("option")
			.first().addBack("[value=\"" + info["provider"] +
			"\"]")
			.last().prop("selected", true);
			me.find("input, textarea")
			.filter("[name=\"ddns_others_url\"]").val(info["others_url"]).end()
			.filter("[name=\"ddns_ipaddr\"][value=\"" +
				(is_local_ipaddr ? "local" : "") +
				"\"]").prop("checked", true).end()
			.filter("[name=\"ddns_username\"]").val(info["username"]).end()
			.filter("[name=\"ddns_password\"]").val(info["password"]).end()
			.filter("[name=\"ddns_password2\"]").val(info["password"]).end()
			.filter("[name=\"ddns_update_all_host\"]").prop("checked", !(info["host"] && info["host"].length)).end()
			.filter("[name=\"ddns_host\"]").val(info["host"].join("\n")).end();

			me.triggerHandler("redraw");
		},
// }}}

		_create_func = function(ref_obj, param) {

			ref_obj = (ref_obj? (ref_obj instanceof jQuery? ref_obj: $(ref_obj)).first(): $());
			if (!ref_obj.length) {
				ref_obj = $("<table/>").addClass("form_table sep").append(
					$("<thead/>").append(
						create_form_title($.i18n("ddns-dynamicDnsSettings"))
					)
				);
			}
			if (!$.isPlainObject(param)) { param = {}; }

			ref_obj
			.off(".ddns_panel")
			.addClass("dynamic_dns_panel")
			.append(_create_ddns_rows());

			ref_obj
			.addClass("ctrl")
			.on("show_ddns_ip_detection_options", function(e) {
				$(this)
				.find("[name=\"ddns_ipaddr\"][value=\"local\"]")
				.prop("checked", true).end()
				.triggerHandler("show_detection");
			});

			ref_obj
			.on("_callback.ddns_panel", param["callback"] || $.noop)
			.on("redraw.ddns_panel", _redraw_method)
			.on("reset.ddns_panel", _set_method)
			.on("set.ddns_panel", _set_method)
			.on("validate.ddns_panel", function() {
				var	_checkDDNSUserFormat = function(s) { return s.match(/^[0-9a-z@_.-]+$/i); },
					me = $(this),
					provider = me.find("select").filter("[name=ddns_provider]").find("option:selected").val(),
					inp = me.find("input,textarea"),
					dn = _get_field_name(provider),
					o, v, is_error,
					i, i_max, arr;
				// [Bug#13796] "Others" Service Provider, by URL in Domain[/Path]
				//	Path checking is according to RFC 3986 Section 3.3
				if (provider == "others") {
					var protocol;
					o = inp.filter("[name=\"ddns_others_url\"]");
					o.val(trim(o.val()));
					if (isempty(o.val())) {
						return err($.i18n("ddns-err-customUrl", dn["ddns_others_url"]), o);
					}
					v = /^(https?:\/\/)?(.*)/.exec(o.val());
					protocol = v[1];
					v = v[2].split("/");
					if (!checkDomainFormat(v[0])) {
						return err($.i18n("err-invalid", dn["ddns_others_url"]), o);
					}
					v.shift();
					is_error = false;
					$.each(v, function(_, v) {
						if (!/^([\w._~!$&'()*+,;=:@-]|(%[0-9a-f]{2}))*$/i.test(v)) {
							is_error = true;
							return false;
						}
					});
					if (is_error) {
						return err($.i18n("err-invalid", dn["ddns_others_url"]), o);
					}
					// [Bug#32591] Support HTTPS URL for WAN Dynamic DNS custom Service provider URL
					if (!protocol) {
						o.val("http://" + o.val());
					}
				}
				switch (provider)
				{
				default:
				case "disable":
					break;
				case "noip":
					// Only no-ip allow ":" and "#" [Bug#12487]
					_checkDDNSUserFormat = function(s) { return s.match(/^[0-9a-z@_.#:-]+$/i); };
				case "changeip":
				case "dyndns":
				case "dnsomatic":
				case "others":
				//	"Name"
					o = inp.filter("[name=\"ddns_username\"]");
					o.val(trim(o.val()));
					if (isempty(o.val()))
					{
						return err($.i18n("err-cannotBeEmpty", dn["ddns_username"]), o);
					}
					if (!_checkDDNSUserFormat(o.val()))
					{
						return err($.i18n("err-invalid", dn["ddns_username"]), o);
					}
				//	"Password" / "Password Confirm"
					o = inp.filter("[name=\"ddns_password\"]");
					if (isempty(o.val()))
					{
						return err($.i18n("err-cannotBeEmpty", dn["ddns_password"]), o);
					}
					if (o.val() != inp.filter("[name=\"ddns_password2\"]").val())
					{
						o.val("");
						inp.filter("[name=\"ddns_password2\"]").val("");
						return err($.i18n("ddns-err-match", dn["ddns_password"]), o);
					}
				//	"Hosts", "Hosts / IDs" on dnsomatic
					o = inp.filter("[name=\"ddns_host\"]");
					if (provider == "dnsomatic" && inp.filter("[name=\"ddns_update_all_host\"]").prop("checked"))
					{
						o.val("");
					}
					else
					{
						arr = o.val().replace(/[ ,\t\r\n]+/g, " ").replace(/^[ ]+|[ ]+$/g, "").split(" ");
						o.val(arr.join("\n"));
						if (isempty(o.val()))
						{
							return err($.i18n("err-cannotBeEmpty", dn["ddns_host"]), o);
						}
						for (i = 0, i_max = arr.length; i < i_max; i++)
						{
							if (provider == "dnsomatic" && checkAlphanumeric(arr[i]))
							{	// [Bug#11245] DNS-O-Matic accepts IDs as alphanumeric string
								continue;
							}
							if (!checkDomainFormat(arr[i]))
							{
								return err($.i18n("ddns-err-host", dn["ddns_host"], arr[i]), o);
							}
						}
					}
					break;
				}
				return true;
			})
			.on("export.ddns_panel", function() {
				var me = $(this);
				var res, o, v;
				if (me.is(":visible")) {
					v = me.find("[name=ddns_provider] option:selected").val();
					res = {
						enable: v != "disable"
					};
					if (res["enable"]) {
						res["provider"] = v;
					}
					switch (res["provider"]) {
					case "others":
						res["customUrl"] = me.find("[name=ddns_others_url]").val();
						// No break intentionally
					case "changeip":
					case "dyndns":
					case "noip":
					case "dnsomatic":
						o = me.find("[name=ddns_ipaddr]");
						res["useWanIp"] = o.filter(":visible:checked").val() == "local";
						res["username"] = me.find("[name=ddns_username]").val();
						res["password"] = me.find("[name=ddns_password]").val();
						o = me.find("[name=ddns_update_all_host]");
						res["host"] = o.is(":visible") && o.is(":checked") ? null :
							me.find("[name=ddns_host]").val().split("\n");
						break;
					default:
						break;
					}
				}
				return res;
			})
			.on("show_detection", function(e) {
				var	me = $(this);
				me.data("show_detection", true);
				me.find("[name=\"ddns_ipaddr\"][value=\"local\"]")
				.prop("checked", true).end()
				me.triggerHandler("redraw");
			})
			.on("change.ddns_panel keyup.ddns_panel", ".ddns_action", function(e) {
				var	obj = $(e.delegateTarget),
					provider_obj = obj.find("select").filter("[name=ddns_provider]"),
					v = provider_obj.val();
				if (provider_obj.data("prev") != v)
				{
					provider_obj.data("prev", v);
					obj.triggerHandler("redraw");
				}
				
			})
			.on("click.ddns_panel change.ddns_panel", ".ddns_update_all", function(e){
				$(e.delegateTarget).triggerHandler("redraw");
			})
			.triggerHandler("reset");
			return ref_obj;
		};

	root.create_ddns_panel = _create_func;
	root.get_ddns_name = function(option) {
		var res;
		$.each(_ddm, function(_, o) {
			if (o[0] == option) {
				res = o[1];
				return false;
			}
		});
		return res || "Unknown";
	};

})(window);

// vim: set foldmethod=marker:
