$(function () {
    "use strict";

    const csrfToken = $('meta[name="csrf-token"]').attr("content");

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type)) {
                xhr.setRequestHeader("X-CSRFToken", csrfToken);
            }
        },
    });

    function api(method, url, data) {
        return $.ajax({
            url: url,
            method: method,
            dataType: "json",
            contentType: "application/json",
            data: data ? JSON.stringify(data) : null,
        });
    }

    function showAlert(message, type) {
        const $alert = $(
            '<div class="alert alert-dismissible fade show" role="alert">' +
                '<span class="alert-text"></span>' +
                '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>' +
            "</div>"
        );
        $alert.addClass("alert-" + (type || "info"));
        $alert.find(".alert-text").text(message);
        $("#message-area").append($alert);
        setTimeout(function () { $alert.alert("close"); }, 5000);
    }

    function errorMessage(xhr) {
        const body = xhr.responseJSON;
        if (body && body.error && body.error.message) {
            return body.error.message;
        }
        if (body && body.detail) {
            return body.detail;
        }
        return "Something went wrong. Please try again.";
    }

    function initHome() {
        const $button = $("#btn-check-health");
        const $result = $("#health-result");

        $button.on("click", function () {
            $button.prop("disabled", true);
            api("GET", $button.data("url"))
                .done(function (res) {
                    $result.removeClass("d-none text-bg-secondary text-bg-danger")
                        .addClass("text-bg-success")
                        .text("Database " + res.database + " (" + res.engine + ")");
                })
                .fail(function (xhr) {
                    $result.removeClass("d-none text-bg-secondary text-bg-success")
                        .addClass("text-bg-danger")
                        .text("Database unreachable");
                    showAlert(errorMessage(xhr), "danger");
                })
                .always(function () {
                    $button.prop("disabled", false);
                });
        });
    }

    const pages = {
        home: initHome,
    };

    const page = $("body").data("page");
    if (pages[page]) {
        pages[page]();
    }

    $(".alert[data-auto-hide]").each(function () {
        const $alert = $(this);
        setTimeout(function () { $alert.alert("close"); }, 5000);
    });
});
