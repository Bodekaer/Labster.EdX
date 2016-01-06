require([
    "domReady", "jquery", "app/collections/license", "app/views/license_list", "app/collections/coach",
    "app/views/coach_selector", "app/utils", "bootstrap"
], function (domReady, $, LicenseCollection, LicenseListView, CoachCollection, CoachSelectorView, utils) {
    domReady(function () {
        var buildLicenseList = _.once(function (collection) {
            var view = new LicenseListView({collection: collection});
            $(document.getElementById("content1")).html(view.$el);

        });
        $coach = $(document.getElementById("coach")).data("metadata");
        var licenseCollection = LicenseCollection.factory();
        window.Labster.coach = $coach;
        buildLicenseList(licenseCollection);
        if (coach) {
            licenseCollection.url = utils.getUrl("licenses", {}, true);
            licenseCollection.fetch();
        } else {
            licenseCollection.reset();
        }


    });
});
