var index;
(() => {
    "use strict";
    var e = {};

    function a() {
        $("#sidebar").removeClass("translate-x-0"), $("#sidebar").addClass("-translate-x-full")
    }

    (e => {
        "undefined" != typeof Symbol && Symbol.toStringTag && Object.defineProperty(e, Symbol.toStringTag, {value: "Module"}), Object.defineProperty(e, "__esModule", {value: !0})
    })(e), $("body").click((function (e) {
        $(e.target).is("#sidebar") || $(e.target).parents().is("#sidebar") || $(e.target).is("#sidebar-toggle-btn") || $(e.target).parents().is("#sidebar-toggle-btn") || a()
    })), $("#sidebar-toggle-btn").click((function (e) {
        $("#sidebar").removeClass("-translate-x-full"), $("#sidebar").addClass("translate-x-0")
    })), $("#sidebar-hide-btn").click((function (e) {
        a()
    })), $(".add-student-btn").click((function () {
        $(".add-student-modal").removeClass("hidden")
    })), $(".add-parent-btn").click((function () {
        $(".add-parent-modal").removeClass("hidden")
    })), $(".add-admin-btn").click((function () {
        $(".add-admin-modal").removeClass("hidden")
    })), $(".add-relationship-btn").click((function () {
        $('.add-relationship-modal input[name="userID"]').val($(this).data("userid")), $(".add-relationship-modal").removeClass("hidden")
    })), $(".add-relationship-parent-btn").click((function () {
        $('.add-relationship-parent-modal input[name="parentID"]').val($(this).data("parentid")), $(".add-relationship-parent-modal").removeClass("hidden")
    })), $(".access-table .info-btn").click((function () {
        $(".access-request-modal p.name").text($(this).data("fullname")), $(".access-request-modal p.relationship").text($(this).data("relationship")), $(".access-request-modal p.info").text($(this).data("info")), $(".access-request-modal p.email").text($(this).data("email")), $(".access-request-modal p.phone").text($(this).data("phone")), $(".access-request-modal").removeClass("hidden")
    })), $(".modal-close-btn").click((function () {
        $(this).closest(".modal").addClass("hidden")
    })), $(".modal-backdrop").click((function () {
        $(this).closest(".modal").addClass("hidden")
    })), $(".checkbox").click((function () {
        var e = $(this).siblings('input[type="checkbox"]');
        console.log(e), e.attr("checked") ? e.attr("checked", !1) : e.attr("checked", !0), $(".checkbox").toggleClass("border-primary bg-gray"), $(".checkbox span").toggleClass("!opacity-100")
    })), $("form").submit((function () {
        $(".loading").removeClass("hidden")
    })), $(".approve-btn").click((function () {
        var e = $(this);
        $.ajax({
            type: "POST",
            url: "/approval-requests/" + $(this).data("action") + "/" + $(this).data("userid") + "/" + $(this).data("requestorid"),
            data: {},
            success: function (a) {
                a.success ? (e.closest("tr").remove(), $(".flash-messages").append(`\n                    <div class="flex w-full border-l-6 border-[#34D399] bg-[#34D399] bg-opacity-[15%] p-4 shadow-md mb-4">\n                        <h5 class="font-medium text-black">\n                            ${a.message}\n                        </h5>\n                    </div>\n                `)) : $(".flash-messages").append(`\n                    <div class="flex w-full border-l-6 border-[#F87171] bg-[#F87171] bg-opacity-[15%] p-4 shadow-md mb-4">\n                        <h5 class="font-medium text-[#B45454]">\n                            ${a.message}\n                        </h5>\n                    </div>\n                `), setTimeout((function () {
                    $(".flash-messages").html("")
                }), 1500)
            }
        })
    })), $(".languages").change((function () {
        location.href = "/switch-language/" + $(this).val()
    })), index = e
})();