require([
    "domReady", "jquery", "app/collections/license", "app/views/license_list", "app/utils", "bootstrap"
], function (domReady, $, LicenseCollection, LicenseListView, utils) {
    domReady(function () {

        var buildLicenseList = _.once(function (collection) {
            var view = new LicenseListView({collection: collection});
            $(document.getElementById("main-content")).html(view.$el);

        });
        var licenseCollection = LicenseCollection.factory();
        buildLicenseList(licenseCollection);
        licenseCollection.url = utils.getUrl("licenses", {}, true);
        licenseCollection.fetch();
    });
});
