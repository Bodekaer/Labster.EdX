define(["backbone", "app/models/coach"], function(Backbone, CoachModel) {
  var CoachCollection = Backbone.Collection.extend({
    sortField: 'full_name',
    model: CoachModel
  }, {
    factory: function(models, options) {
      return new CoachCollection(models, options);
    }
  });

  return CoachCollection;
});
