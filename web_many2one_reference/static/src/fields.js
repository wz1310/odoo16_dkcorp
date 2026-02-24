odoo.define('web_many2one_reference.fields', function (require) {
    "use strict";
    
    var AbstractField = require('web.AbstractField');
    var basicFields = require('web.basic_fields');
    var FieldMany2One = require('web.relational_fields').FieldMany2One;
    var FieldInteger = basicFields.FieldInteger;
    var concurrency = require('web.concurrency');
    var ControlPanelView = require('web.ControlPanelView');
    var core = require('web.core');
    var data = require('web.data');
    var Dialog = require('web.Dialog');
    var dialogs = require('web.view_dialogs');
    var dom = require('web.dom');
    var KanbanRecord = require('web.KanbanRecord');
    var KanbanRenderer = require('web.KanbanRenderer');
    var ListRenderer = require('web.ListRenderer');
    var Pager = require('web.Pager');
    var registry = require('web.field_registry');
    var BasicModel = require('web.BasicModel');
    var field_utils = require('web.field_utils');

    var _t = core._t;
    var _lt = core._lt;
    var qweb = core.qweb;


    BasicModel.include({
        _getDomain: function (element, options) {
            if(element.fieldsInfo.form && element.fieldsInfo.form[options.fieldName].widget=='M2oReference'){
                return []
            }else{
                return this._super(element, options)
            }
        },
        _fetchIntegerReference: function (record, fieldName) {
            var self = this;
            var def;
            var value = record._changes && record._changes[fieldName] || record.data[fieldName];
            var model_field_name = record.fieldsInfo.form[fieldName].options.model_field;
            var model = record._changes && record._changes[model_field_name] || record.data[model_field_name];
            var resID = value
            if (model && model !== 'False' && resID) {
                def = self._rpc({
                    model: model,
                    method: 'name_get',
                    args: [resID],
                    context: record.getContext({fieldName: fieldName}),
                }).then(function (result) {
                    return self._makeDataPoint({
                        data: {
                            id: result[0][0],
                            display_name: result[0][1],
                        },
                        modelName: model,
                        parentID: record.id,
                    });
                });
            }
            return Promise.resolve(def);
        },
        _fetchSpecialReference: function (record, fieldName) {
            var def;
            var field = record.fields[fieldName];
            if (field.type === 'char') {
                // if the widget reference is set on a char field, the name_get
                // needs to be fetched a posteriori
                def = this._fetchReference(record, fieldName);
            }else if(field.type === 'integer'){

                def = this._fetchIntegerReference(record, fieldName);
            }
            return Promise.resolve(def);
        },
    })



    var FieldMany2OneReference = FieldMany2One.extend({
        specialData:"_fetchSpecialReference",

        _manageSearchMore: function (values, search_val, domain, context) {
            var self = this;
            values = values.slice(0, this.limit);
            
            var rel = this._get_rel_val()
            values.push({
                label: _t("Search More..."),
                action: function () {
                    var prom;
                    if (search_val !== '') {
                        prom = self._rpc({
                            model: rel,
                            method: 'name_search',
                            kwargs: {
                                name: search_val,
                                args: domain,
                                operator: "ilike",
                                limit: self.SEARCH_MORE_LIMIT,
                                context: context,
                            },
                        });
                    }
                    Promise.resolve(prom).then(function (results) {
                        var dynamicFilters;
                        if (results) {
                            var ids = _.map(results, function (x) {
                                return x[0];
                            });
                            dynamicFilters = [{
                                description: _.str.sprintf(_t('Quick search: %s'), search_val),
                                domain: [['id', 'in', ids]],
                            }];
                        }
                        self._searchCreatePopup("search", false, {}, dynamicFilters);
                    });
                },
                classname: 'o_m2o_dropdown_option',
            });
            return values;
        },
        _get_rel_val: function(){
            var model_field = this.nodeOptions.model_field;
            var rel = this.__parentedParent.state.data && this.__parentedParent.state.data[model_field] || this.record.data[this.nodeOptions.model_field]
            return rel
        },
        _getSearchCreatePopupOptions: function(view, ids, context, dynamicFilters) {
            var self = this;
            
            var rel = this._get_rel_val()
            return {
                res_model: rel,
                domain: this.record.getDomain({fieldName: this.name}),
                context: _.extend({}, this.record.getContext(this.recordParams), context || {}),
                dynamicFilters: dynamicFilters || [],
                title: (view === 'search' ? _t("Search: ") : _t("Create: ")) + this.string,
                initial_ids: ids,
                initial_view: view,
                disable_multiple_selection: true,
                no_create: !self.can_create,
                kanban_view_ref: this.attrs.kanban_view_ref,
                on_selected: function (records) {
                    self.reinitialize(records[0]);
                },
                on_closed: function () {
                    self.activate();
                },
            };
        },
        _renderEdit: function(){
            return this._super()
        },
        reset: function (record, event) {
            this._reset(record, event);
            if (!event || event === this.lastChangeEvent) {
                this.isDirty = false;
            }
            this._resetFieldRelation()
            if (this.isDirty) {
                return Promise.resolve();
            } else {
                return this._render();
            }
        },
        _reset: function () {
            this._super.apply(this, arguments);
            this._resetFieldRelation();
            this.floating = false;
            this.m2o_value = this._formatValue(this.value);
        },
        _fetch_value_display: function(value){
            var self = this
            return self._rpc({
                model: self.field.relation,
                method: 'search_read',
                fields: ['display_name'],
                domain: [['id', '=', value]],
            })
        },
        _parseValue: function (value) {
            var parsed = field_utils.parse['many2one'](value, this.field, this.parseOptions);
            return parsed.id
        },
        _formatValue: function () {
            var value;
            if(this.value==0){
                return ""
            }
            if (this.field.type === 'integer') {
                if(!this.field.relation){
                    this._resetFieldRelation()
                }
                value = this.record.specialData[this.name]
            } else {
                value = this.value;
            }
            return value && value.data && value.data.display_name || '';
        },

        init: function (parent, name, record, options) {
            // this._super.apply(arguments)
            var sup = this._super(parent, name, record, options)
            this._resetFieldRelation()
            
            return sup
        },
        _resetFieldRelation:function(){
            if(this.nodeOptions.model_field){
                var model_field = this.nodeOptions.model_field;
                var rel = this.__parentedParent.state.data && this.__parentedParent.state.data[model_field] || this.record.data[this.nodeOptions.model_field]
                this._setRelation(rel)
            }
            
        },
        _setValue: function (value, options) {
            return this._super(value,options)
        },
        _setRelation: function (model) {
            // used to generate the search in many2one
            this.field.relation = model;
        },

        _search: function (search_val) {
            var self = this;
            var def = new Promise(function (resolve, reject) {
                var context = self.record.getContext(self.recordParams);
                var domain = self.record.getDomain(self.recordParams);
    
                // Add the additionalContext
                _.extend(context, self.additionalContext);
    
                var blacklisted_ids = self._getSearchBlacklist();
                if (blacklisted_ids.length > 0) {
                    domain.push(['id', 'not in', blacklisted_ids]);
                }
                var model_name = self.nodeOptions.model_field
                self._rpc({
                    model: self.field.relation || self.__parentedParent.state.data[model_name],
                    method: "name_search",
                    kwargs: {
                        name: search_val,
                        args: domain,
                        operator: "ilike",
                        limit: self.limit + 1,
                        context: context,
                    }}).then(function (result) {
                    // possible selections for the m2o
                    var values = _.map(result, function (x) {
                        x[1] = self._getDisplayName(x[1]);
                        return {
                            label: _.str.escapeHTML(x[1].trim()) || data.noDisplayContent,
                            value: x[1],
                            name: x[1],
                            id: x[0],
                        };
                    });
    
                    // search more... if more results than limit
                    if (values.length > self.limit) {
                        values = self._manageSearchMore(values, search_val, domain, context);
                    }
                    var create_enabled = self.can_create && !self.nodeOptions.no_create;
                    // quick create
                    var raw_result = _.map(result, function (x) { return x[1]; });
                    if (create_enabled && !self.nodeOptions.no_quick_create &&
                        search_val.length > 0 && !_.contains(raw_result, search_val)) {
                        values.push({
                            label: _.str.sprintf(_t('Create "<strong>%s</strong>"'),
                                $('<span />').text(search_val).html()),
                            action: self._quickCreate.bind(self, search_val),
                            classname: 'o_m2o_dropdown_option'
                        });
                    }
                    // create and edit ...
                    if (create_enabled && !self.nodeOptions.no_create_edit) {
                        var createAndEditAction = function () {
                            // Clear the value in case the user clicks on discard
                            self.$('input').val('');
                            return self._searchCreatePopup("form", false, self._createContext(search_val));
                        };
                        values.push({
                            label: _t("Create and Edit..."),
                            action: createAndEditAction,
                            classname: 'o_m2o_dropdown_option',
                        });
                    } else if (values.length === 0) {
                        values.push({
                            label: _t("No results to show..."),
                        });
                    }
    
                    resolve(values);
                });
            });
            this.orderer.add(def);
            return def;
        },
    });

    registry
        .add('M2oReference', FieldMany2OneReference)

    return {
        FieldMany2OneReference:FieldMany2OneReference
    }

})