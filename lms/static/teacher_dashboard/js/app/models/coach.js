define(["backbone"], function(Backbone) {
  var CoachModel = Backbone.Model.extend({
    defaults: {
      "full_name": null,
      "email": null
    },

    getTitle: function() {
      return this.get("full_name") || this.get("email");
    }
  });

  return CoachModel;
});
