define([
  "app/views/base", "underscore", "text!templates/coach_selector.underscore"
], function(BaseView, _, CoachSelectorTemplate) {
  var CoachSelectorView = BaseView.extend({
    tagName: "div",
    className: "row form-group coach-selector",
    template: _.template(CoachSelectorTemplate),
    events: {"change select": "onChange"},

    getContext: function() {return {collection: this.collection};},

    onChange: function(event) {
      var value = $(event.target).val();
      if (_.isFunction(this.options.onChange)) {
        this.options.onChange(value);
      }
    }
});

  return CoachSelectorView;
});
