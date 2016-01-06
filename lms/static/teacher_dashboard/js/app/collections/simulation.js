define([
  "backbone", "underscore", "app/models/simulation", "app/utils"
], function(Backbone, _, SimulationModel, utils) {
  var SimulationCollection = Backbone.Collection.extend({
    comparator: "display_name",
    model: SimulationModel,

    constructor: function(models, options) {
      Backbone.Collection.prototype.constructor.apply(this, arguments);
      this.options = options;
    },

    parse: function(response) {
      if (this.options && _.isUndefined(this.options.license)) {
        return response;
      }

      return _.map(response, function(rawModel) {
        rawModel.license = this.options.license;
        return rawModel;
      }, this);
    },

    toJSON: function(data) {
      return _.map(response, function(rawModel) {
        delete data.license;
        return rawModel;
      }, this);
    }
  }, {
    factory: function(models, options, license_id) {
      var collection;

      options = _.extendOwn({license: license_id}, options);
      collection =  new SimulationCollection(models, options);
      collection.url = utils.getUrl("simulations", {license_id: license_id}, false);
      return collection;
    }
  });

  return SimulationCollection;
});
