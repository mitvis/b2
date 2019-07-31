from __future__ import absolute_import

from pandas import DataFrame, read_csv, read_json
from typing import Dict, Optional, List, Callable, Union, cast
from datetime import datetime
from json import loads

# from IPython.display import display, publish_display_data

from .errors import check_not_null, NullValueError
from .showme import gen_spec, set_data_attr, SELECTION_SIGNAL
from .widget import MidasWidget
from .types import DFInfo, ChartType, TwoDimSelectionPredicate, OneDimSelectionPredicate, SelectionPredicate, Channel, DFDerivation, DerivationType, DFLoc, TickItem, JoinInfo, Visualization, PredicateCallback, TickCallbackType, DataFrameCall, PredicateCall

CUSTOM_FUNC_PREFIX = "__m_"
MIDAS_INSTANCE_NAME = "m"

class Midas(object):
    """[summary]
    
    functions prefixed with "js_" is invoked by the js layer.
    """
    dfs: Dict[str, DFInfo]
    tick_funcs: Dict[str, List[TickItem]]
    joins: List[JoinInfo]

    def __init__(self, m_name=MIDAS_INSTANCE_NAME):
        self.dfs = {}
        self.tick_funcs = {}
        self.m_name: str = m_name
        print("Initiated Midas")
        # TODO: maybe we can just change the DataFrame here...
        # self._pandas_magic()

    def loc(self, df_name: str, new_df_name: str, rows: Optional[Union[slice, List[int]]] = None, columns: Optional[Union[slice, List[str]]] = None) -> DataFrame:
        """this is a wrapper around the DataFrame `loc` function so that Midas will
        help keep track
        
        Arguments:
            df_name {str} -- [description]
            new_df_name {str} -- [description]
            columns {slice} -- [description]
            rows {slice} -- [description]
        
        Returns:
            DataFrame -- the new dataframe that's is returned 
        """
        # need to pass in, named, df, rows, columns, and the new name of the df
        found = self.dfs[df_name]
        filled_rows = rows if rows else slice(None, None, None)
        filled_columns = columns if columns else slice(None, None, None)
        new_df = found.df.loc[filled_rows, filled_columns]
        loc_spec = DFLoc(filled_rows, filled_columns)
        self.register_df(new_df, new_df_name, DFDerivation(df_name, new_df_name, DerivationType.loc, loc_spec))
        return new_df

    # def _pandas_magic(self):
    #     old_loc = DataFrame.loc
    #     # s is self.
    #     DataFrame.m_loc = new_loc


    def df(self, df_name: str):
        # all the dfs are named via the global var so we can manipulate without worrying about reference changes!
        found = self.dfs[df_name]
        if (found != None):
            return found.df
        else:
            return None


    def register_df(self, df: DataFrame, df_name: str, derivation=None):
        """pivate method to keep track of dfs
            TODO: make the meta_data work with the objects
        """

        created_on = datetime.now()
        selections: List[SelectionPredicate] = []
        chart_spec = None # to be populated later
        df_info = DFInfo(df_name, df, created_on, selections, derivation, chart_spec)
        self.dfs[df_name] = df_info
        self.__show_or_rename_visualization()


    def remove_df(self, df_name: str):
        self.dfs.pop(df_name)


    def __show_or_rename_visualization(self):
        # raise NotImplementedError("__show_visualization needs to understand event between phospher")
        print("showing visualization")


    def get_current_widget(self):
        # TODO: show all the dfs (cut off at 5)
        current_obj = max(self.dfs.values(), key=lambda v: v.created_on)
        if ((current_obj != None) & (current_obj.df_name != None)):
            df_name = current_obj.df_name
            print(df_name)
            return self.visualize_df_without_spec(df_name)
        else:
           return


    def read_json(self, path: str, df_name: str, **kwargs):
        df = read_json(path, kwargs)
        self.register_df(df, df_name)
        return df


    def read_csv(self, path: str, df_name: str, **kwargs):
        df = read_csv(path, kwargs)
        # meta_data = DfMetaData(time_created = datetime.now())
        self.register_df(df, df_name)
        return df


    def get_df_to_visualize_from_context(self):
        # if (df_name == None):
        #     df = self.get_df_to_visualize_from_context()
        # el
        
        raise NotImplementedError()


    # note that spec is defaulted to none without the Optional signature because there is no typing for JSON.
    def visualize_df(self, df_name: str, spec=None):
        # generate default spec
        if (spec == None):
            # see if it's stored
            vis = self.dfs[df_name].visualization
            if vis:
                stored_spec = vis.chart_spec
            else:
                raise NullValueError('visualization should be set by now')
            if (stored_spec != None):
                return self.visualize_df_with_spec(df_name, stored_spec, True)
            return self.visualize_df_without_spec(df_name)
        else:
            return self.visualize_df_with_spec(df_name, spec, True)

    def visualize(self, df_name: str):
        # just an alias
        return self.visualize_df_without_spec(df_name)

    def visualize_df_without_spec(self, df_name: str):
        df = self.df(df_name)
        spec = gen_spec(df)
        # set_data is false because gen_spec already sets the data
        return self.visualize_df_with_spec(df_name, spec, False)


    def _tick(self, df_name: str):
        # checkthe tick item
        items = self.tick_funcs.get(df_name)
        if items:
            _items = items
            for i in _items:
                if (i.callback_type == TickCallbackType.predicate):
                    p = self.get_selection_by_predicate(df_name)
                    if p:
                        i.call.func(p)
                    return
                else:
                    _call = cast(DataFrameCall, i.call)
                    new_data = _call.func(self.get_selection_by_df(df_name))
                    # send the update
                    vis = self.dfs[_call.target_df].visualization
                    if vis:
                        vis.widget.replaceData()
                # now push the new_data to the relevant widget

    def js_add_selection(self, df_name: str, selection: str):
        # DataFrame
        # figure out what spec it was
        df_info = self.dfs[df_name]
        check_not_null(df_info)
        predicate_raw = loads(selection)
        interaction_time = datetime.now()
        vis = df_info.visualization
        predicate: SelectionPredicate
        if vis:
            if (vis.chart_spec.chart_type == ChartType.scatter):
                x_column = vis.chart_spec.encodings[Channel.x]
                y_column = vis.chart_spec.encodings[Channel.y]
                predicate = TwoDimSelectionPredicate(interaction_time, x_column, y_column, predicate_raw.x, predicate_raw.y)
            else:
                x_column = vis.chart_spec.encodings[Channel.x]
                predicate = OneDimSelectionPredicate(interaction_time, x_column, predicate_raw.x)
            df_info.predicates.append(predicate)
            self._tick(df_name)
        return
        
    def get_selection_by_predicate(self, df_name: str):
        df_info = self.dfs[df_name]
        check_not_null(df_info)
        if (len(df_info.predicates) > 0):
            predicate = df_info.predicates[-1]
            return predicate
        return None


    def get_selection_by_df(self, df_name: str):
        """get_selection returns the selection DF with the optional columns specified
        The default would be the selection of all of the df
        However, if some column is not in the rows of the df are specified, Midas will try to figure out based on the derivation history what is going on.
        
        Arguments:
            df_name {str} -- [description]
        
        Returns:
            [type] -- [description]
        """
        # MAYBE TODO: add columns: Optional[List[str]]=None
        # take the predicate and generate the dataframe
        df_info = self.dfs[df_name]
        check_not_null(df_info)
        if (len(df_info.predicates) > 0):
            predicate = df_info.predicates[-1]
            if (isinstance(predicate, OneDimSelectionPredicate)):
                # .dim == 1):
                # FIXME: the story around categorical is not clear
                selection_df = df_info.df.loc[
                      (df_info.df[predicate.x_column] < predicate.x[1])
                    & (df_info.df[predicate.x_column] < predicate.x[0])
                ]
                return selection_df
            else:
                # new_predicate: TwoDimSelectionPredicate(predicate)
                selection_df = df_info.df.loc[
                      (df_info.df[predicate.x_column] < predicate.x[1])
                    & (df_info.df[predicate.x_column] < predicate.x[0])
                    & (df_info.df[predicate.x_column] > predicate.y[0])
                    & (df_info.df[predicate.x_column] < predicate.y[1])
                ]
                return selection_df
        else:
            # return no result
            col_names =  df_info.df.columns
            empty_df = DataFrame(columns = col_names)
            return empty_df


    def get_selection_history(self, df_name: str):
        found = self.dfs[df_name]
        if (found != None):
            return found.predicates
        else:
            return None 

    def _add_to_tick(self, df_name: str, item: TickItem):
        if (df_name in self.tick_funcs):
            self.tick_funcs[df_name].append(item)
        else:
            self.tick_funcs[df_name] = [item]

    def add_callback_to_selection(self,
        df_name: str,
        cb: PredicateCallback
      ):
        # we'll put this inside the python so it's not all generated by the janky JS
        call = PredicateCall(cb)
        item = TickItem(TickCallbackType.predicate, call)
        self._add_to_tick(df_name, item)

        return

    
    def new_visualization_from_selection(self, df_interact_name: str, new_df_name: str, df_transformation: Callable[[DataFrame], DataFrame]):
        """
        This is used for blackbox style visualizations
    
        Arguments:
            df_interact_name {str} -- specify the interaction whose selection will be used as the basis
            new_df_name {str} -- [description]
            df_transformation {Callable[[DataFrame], DataFrame]} -- [description]
        
        Raises:
            NotImplementedError: [description]
        """
        call = DataFrameCall(df_transformation, new_df_name)
        item = TickItem(TickCallbackType.dataframe, call)
        self._add_to_tick(df_interact_name, item)
        return


    def register_join_info(self, dfs: List[str], join_columns: List[str]):
        join_info = JoinInfo(dfs, join_columns)
        self.joins.append(join_info)


    def addFacet(self, df_name: str, facet_column: str):
        # 
        raise NotImplementedError()


    def link_dfs(self, df_interact_name: str, new_df_name: str):
        # infer how  df_interact_name and df_filter_name are connected to each other
        # the simplest case is that they are both columns from a large existing table
        # basically re-write the otherone if we know how to
        # then do similar as new_visualization_from_selection
        # use the predicate to link them together

        # case 1: two dfs derived from the same original df, both using loc
        #         then we can either create a new Vega spec with data, using loc
        #         or we can just go through the predicate construction via the df logic?
        #         #TODO: ask Arvind?
        raise NotImplementedError()


    def visualize_df_with_spec(self, df_name: str, spec, set_data=False):
        if (set_data):
            df = self.df(df_name)
            # note that we need to assign to a new variable, otherwise it will not load
            spec_with_data = set_data_attr(spec, df)
        else:
            spec_with_data = spec
        # register the spec to the df
        w = MidasWidget(spec_with_data)
        # items[node.ind] = items[node.ind]._replace(v=node.v)

        self.dfs[df_name] = self.dfs[df_name]._replace(visualization = Visualization(spec, w))
        cb = f"""
            var {CUSTOM_FUNC_PREFIX}val_str = JSON.stringify(value);
            var pythonCommand = `
                from json import loads
                from pandas import DataFrame
                {CUSTOM_FUNC_PREFIX}loaded_data = loads('${{{CUSTOM_FUNC_PREFIX}val_str}}')
                {CUSTOM_FUNC_PREFIX}select_df = DataFrame({CUSTOM_FUNC_PREFIX}loaded_data, index=[0])
                {self.m_name}.add_selection("{df_name}", {CUSTOM_FUNC_PREFIX}select_df)
            `;
            console.log('pythonCommand', pythonCommand);
            IPython.notebook.kernel.execute(pythonCommand);
        """
        w.register_signal_callback(SELECTION_SIGNAL, cb)
        return w


__all__ = ['Midas']
