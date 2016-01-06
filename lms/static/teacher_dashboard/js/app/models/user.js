define(["backbone", "app/utils"], function(Backbone, utils) {
  var UserModel = Backbone.Model.extend({
    defaults: {
      "full_name": null,
      "email": null,
      "attempts_count": 0,
      "time": 0,
      "score": 0,
      "questions_answered": 0
    },

    getTime: function() {
      return _.isNull(this.get("time")) ? "-" : utils.time(this.get("time"));
    },

    getDisplayName: function() {
      return this.get("full_name") || this.get("email");
    }
  });

  return UserModel;
});
