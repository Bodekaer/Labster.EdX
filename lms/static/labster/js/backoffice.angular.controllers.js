angular.module('LabsterBackOffice')

  .controller('LicenseListController', function ($scope, $http) {
    $scope.licenses = [];

    var url = window.backofficeUrls.license;
    $http.get(url, {
      headers: {
        'Authorization': "Token " + window.requestUser.backoffice.token
      }
    })

      .success(function (data, status, headers, config) {
        angular.forEach(data, function (item) {
          item.end_date = moment(item.date_end_license).format('ll');
          item.date_bought = moment(item.date_bought).format('ll');
        });

        $scope.licenses = data;
      });

    $scope.payments = [];

    // unpaid payment url
    var url_payment = window.backofficeUrls.payment + '?status=0';
    $http.get(url_payment, {
      headers: {
        'Authorization': "Token " + window.requestUser.backoffice.token
      }
    })

      .success(function (data, status, headers, config) {
        angular.forEach(data, function (payment) {
          payment.detail_url = '#/invoice/' + payment.id;
          payment.created_date = moment(payment.created_at).format('ll');
        });

        $scope.payments = data;
      });

  })

  .controller('NewPersonalLicenseController', function ($scope, $location, $http) {
    $scope.labs = [];
    $scope.showLabForm = false;
    $scope.totalPrice = 0;
    $scope.isProcessing = false;
    $scope.checkoutButton = "Checkout";

    angular.forEach(window.labList, function (lab) {
      lab.license = 0;
      lab.total = 0;

      $scope.labs.push(lab);
    });

    $scope.updateTotal = function () {
      $scope.totalPrice = 0;
      angular.forEach($scope.labs, function (lab) {
        // set default value to 0 if the field is empty
        var length = lab.license.toString().length;
        if (length == 0) {
          lab.license = 0;
        }

        lab.total = lab.license * lab.price;
        $scope.totalPrice += lab.total;
        lab.total = lab.total.toFixed(2);

      });
      $scope.totalPrice = $scope.totalPrice.toFixed(2);
    };

    $scope.resetCount = function (lab) {
      lab.license = 0;
      lab.total = 0;
      $scope.updateTotal();
    };

    var duplicateLabs = function (list_product, callback) {
      callback();
      return;

      var labs = [],
        post_data;
      angular.forEach(list_product, function (item) {
        labs.push({
          lab_id: item.product,
          license_count: item.item_count
        });
      });

      var post_data = {labs: labs};
      var url = window.backofficeUrls.duplicateLabs;
      $http.post(url, post_data, {
        headers: {
          'Authorization': "Token " + window.requestUser.token
        }
      }).success(function (data, status, headers, config) {
        callback();
      }).error(function (data, status, headers, config) {
      });
    };

    $scope.buyLabs = function () {
      var list_product;

      $scope.isProcessing = true;
      $scope.checkoutButton = "Processing";
      var url = window.backofficeUrls.buyLab;
      data = {
        user: window.requestUser.backoffice.user.id,
        payment_type: "manual",
        list_product: []
      };

      angular.forEach($scope.labs, function (lab) {
        if (lab.license > 0) {
          data.list_product.push({
            product: lab.id,
            item_count: lab.license,
            month_subscription: lab.month_subscription
          });
        }
      });

      list_product = data.list_product;
      $http.post(url, data, {
        headers: {
          'Authorization': "Token " + window.requestUser.backoffice.token
        }
      })

        .success(function (data, status, headers, config) {
          duplicateLabs(list_product, function () {
            var url = '/invoice/' + data.id;
            $location.url(url);
          });
        })

        .error(function (data, status, headers, config) {
        });

    }
  })

  .controller('PaymentListController', function ($scope, $http) {
    $scope.payments = [];

    var url = window.backofficeUrls.payment;
    $http.get(url, {
      headers: {
        'Authorization': "Token " + window.requestUser.backoffice.token
      }
    })

      .success(function (data, status, headers, config) {
        angular.forEach(data, function (payment) {
          payment.detail_url = '#/invoice/' + payment.id;
          payment.created_date = moment(payment.created_at).format('ll');
        });

        $scope.payments = data;
      });

  })

  .controller('PaymentDetailController', function ($scope, $routeParams, $http, ngDialog) {
    $scope.user = window.requestUser;
    $scope.payment = null;
    $scope.show_information = false;

    var paymentId = $routeParams.paymentId;
    var url = window.backofficeUrls.payment + paymentId + "/";

    $scope.pop_up_open = function () {
      ngDialog.open({ template: "invoice_information" });
    };

    $http.get(url)
      .success(function (data, status, headers, config) {
        data.total_in_cent = parseFloat(data.total) * 100;
        data.total = parseFloat(data.total).toFixed(2);
        data.created_date = moment(data.created_at).format('ll');
        $scope.payment = data;
      });

    $scope.payment_description = function (payment_products, total) {
      var lab_count = 0;
      var total_license = 0;
      angular.forEach(payment_products, function (product) {
        lab_count++;
        total_license += product.item_count;
      });
      return lab_count + " labs with " + total_license + " licenses. ($" + total + ")";
    };

    $scope.invoiceId = "00" + paymentId;
  })

  .controller('PaymentPaidController', function ($scope, $routeParams) {
    var paymentId = $routeParams.paymentId;
    $scope.detailUrl = window.backofficeUrls.payment + paymentId;
  })

  .controller('HomeController', function ($scope) {
  });
