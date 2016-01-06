window.require = {
  baseUrl: "/static/teacher_dashboard/js",
  paths: {
      "jquery": [
        "//ajax.googleapis.com/ajax/libs/jquery/1.11.2/jquery.min",
        //If the CDN location fails, load from this location
        "vendor/jquery-1.11.2.min"
      ],
      "moment": [
        "//cdnjs.cloudflare.com/ajax/libs/moment.js/2.10.6/moment.min",
        //If the CDN location fails, load from this location
        "vendor/moment.min"
      ],
      "bootstrap": "vendor/bootstrap.min",
      "backbone": "vendor/backbone-min",
      "underscore": "vendor/underscore-min",
      "domReady": "vendor/domReady",
      "jquery.sticky": "vendor/jquery.sticky-kit.min",
      "URI": "vendor/URI",
      "text": "vendor/text"
  },
  shim: {
      "bootstrap": {
          deps: ["jquery"]
      },
      "jquery.sticky": {
          deps: ["jquery"]
      }
  }
};
