/// <reference path="../external/Jupyter.d.ts" />
import React, { MouseEventHandler } from "react";
import {
  SortableContainer,
  SortableElement,
  SortableHandle,
} from "react-sortable-hoc";
import { makeElementId } from "../config";
import { View } from "vega";
// we are going to be rendering vega-lite now for its superior layout etc.
import { TopLevelSpec } from "vega-lite";
import vegaEmbed from "vega-embed";
import { SELECTION_SIGNAL, DEFAULT_DATA_SOURCE, DEBOUNCE_RATE } from "../constants";
import { LogDebug, LogInternalError, getDfId } from "../utils";
import CellState from "../CellState";
import { EncodingSpec, genVegaSpec } from "../charts/vegaGen";

interface MidasElementProps {
  changeStep: number;
  cellId: number;
  removeChart: MouseEventHandler;
  dfName: string;
  title: string;
  encoding: EncodingSpec;
  tick: (dfName: string) => void;
  cellState: CellState;
  data: any[];
  comm: any; // unfortunately not typed
}

interface MidasElementState {
  elementId: string;
  hidden: boolean;
  view: View;
  currentBrush: string;
}

const DragHandle = SortableHandle(() => <span className="drag-handle"><b>&nbsp;⋮⋮&nbsp;</b></span>);
// in theory they should each have their own call back,
// but in practice, there is only one selection happening at a time due to single user

function getDebouncedFunction(dfName: string, tick: (dfName: string) => void, cellState: CellState, addSelection: (selection: string) => void) {
  const callback = (signalName: string, value: any) => {
    // also need to call into python state...
    let valueStr = JSON.stringify(value);
    valueStr = (valueStr === "null") ? "None" : valueStr;
    cellState.addSelectionToPython(dfName, valueStr);
    addSelection(valueStr);
    LogDebug("Sending to comm the selection");
    tick(dfName);
  };

  const wrapped = (name: any, value: any) => {
    const n = new Date();
    let l = (window as any).lastInvoked;
    (window as any).lastInvoked = n;
    if (l) {
      if ((n.getTime() - l.getTime()) < DEBOUNCE_RATE) {
        clearTimeout((window as any).lastInvokedTimer);
      }
      (window as any).lastInvokedTimer = setTimeout(() => callback(name, value), DEBOUNCE_RATE);
    } else {
      l = n;
    }
  };
  return wrapped;
}


/**
 * Contains the visualization as well as a header with actions to minimize,
 * delete, or find the corresponding cell of the visualization.
 */
export class MidasElement extends React.Component<MidasElementProps, MidasElementState> {
  constructor(props: any) {
    super(props);
    this.embed = this.embed.bind(this);
    this.addBrush = this.addBrush.bind(this);

    const elementId = makeElementId(this.props.dfName, false);
    this.state = {
      hidden: false,
      view: null,
      elementId,
      currentBrush: null,
    };
  }

  componentDidMount() {
    // FIXME: maybe do not need to run everytime???
    this.embed();
  }

  addBrush(selectionStr: string) {
    if (selectionStr === this.state.currentBrush) {
      LogDebug(`add brush called ${selectionStr}, NOOP`);
      return;
    }
    const selection = JSON.parse(selectionStr);
    // @ts-ignore
    const scale = this.state.view.scale;
    const signal = this.state.view.signal;
    const encoding = this.props.encoding;
    if (selection[encoding.x]) {
      const x_pixel_min = scale("x")(selection[encoding.x][0]);
      const l = selection[encoding.x].length;
      const x_pixel_max = scale("x")(selection[encoding.x][l - 1]);
      // and update the brush_x and brush_y
      signal("brush_x", [x_pixel_min, x_pixel_max]);
    }
    if (selection[encoding.y]) {
      const y_pixel_min = scale("y")(selection[encoding.y][0]);
      const y_pixel_max = scale("y")(selection[encoding.y][1]);
      // and update the brush_y and brush_y
      signal("brush_y", [y_pixel_min, y_pixel_max]);
    }
    return;
  }


  embed() {
    const { dfName, encoding, data, tick, cellState } = this.props;
    const vegaSpec = genVegaSpec(encoding, dfName, data);
    const addSelect = (currentBrush: string) => { this.setState({currentBrush}); };
    // @ts-ignore
    vegaEmbed(`#${this.state.elementId}`, vegaSpec)
      .then((res: any) => {
        const view = res.view;
        this.setState({
          view,
        });
        res.view.addSignalListener(SELECTION_SIGNAL, getDebouncedFunction(dfName, tick, cellState, addSelect));
      })
      .catch((err: Error) => console.error(err));
  }

  /**
   * Toggles whether the visualization can be seen
   */
  toggleHiddenStatus() {
    this.setState(prevState => {
      return { hidden: !prevState.hidden };
    });
  }


  // componentWillReceiveProps(nextProps: MidasElementProps) {
  //   if (nextProps.changeStep > this.props.changeStep) {
  //     }
  // }

  /**
   * Selects the cell in the notebook where the data frame was defined.
   * Note that currently if the output was generated and then the page
   * is refreshed, this may not work.
   */
  selectCell() {
    const cell = Jupyter.notebook.get_msg_cell(this.props.cellId);
    const index = Jupyter.notebook.find_cell_index(cell);
    Jupyter.notebook.select(index);
    const cell_div = Jupyter.CodeCell.msg_cells[this.props.cellId];
    if (cell_div) {
      cell_div.code_mirror.display.lineDiv.scrollIntoViewIfNeeded();
    }
  }

  // FIXME: figure out the type...
  async replaceData(newValues: any) {
    if (!this.state.view) {
      LogInternalError(`Vega view should have already been defined by now!`);
    }
    // can do this in python too
    const changeSet = this.state.view
      .changeset()
      .remove((datum: any) => {return datum.is_overview === 0; })
      .insert(newValues);

    this.state.view.change(DEFAULT_DATA_SOURCE, changeSet).runAsync();
  }

  addSelectionButtonClicked() {
    this.props.comm.send({
      "command": "add_selection",
      "df_name": this.props.title
    });
  }

  /**
   * Renders this component.
   */
  render() {
    return (
      <div className="card midas-element" id={getDfId(this.props.dfName)}>
        <div className="midas-header">
          <DragHandle/>
          <span className="midas-title">{this.props.title}</span>
          <div className="midas-header-options"></div>
          <button
            className={"midas-header-button"}
            onClick={() => this.selectCell()}
          >cell</button>
          <button
            className={"midas-header-button"}
            onClick={() => this.addSelectionButtonClicked()}
          >clip</button>
          <button
            className={"midas-header-button"}
            onClick={() => this.toggleHiddenStatus()}>
            {this.state.hidden ? "+" : "-"}
          </button>
          <button
            className={"midas-header-button"}
            onClick={(e) => this.props.removeChart(e)}>
            x
          </button>
        </div>
        <div
          id={this.state.elementId}
          style={this.state.hidden ? { display: "none" } : {}}
        />
      </div>
    );
  }
}

// const SortableItem = SortableElement((props: MidasElementProps) => (
//   <div className="sortable">
//     <MidasElement {...props}/>
//   </div>
// ), {withRef: true});

// export default SortableItem;

export default MidasElement;