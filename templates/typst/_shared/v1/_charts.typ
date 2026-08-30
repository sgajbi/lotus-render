// Native chart primitives for the Lotus reporting visual system.
//
// These replace hand-built SVG strings assembled in Python. Three reasons, in order of
// how much they cost:
//
// 1. An SVG containing `<text>` sits on an open Typst non-determinism bug
//    (typst#6783): the PDF's font sections for two text styles can swap order between
//    otherwise identical renders. The performance chart emitted nine `<text>` elements,
//    so every render was relying on luck the fingerprint would not have caught.
// 2. Chart chrome built by hand goes wrong quietly. #152 shipped two of five gridlines
//    outside the plot, one below the axis and one off the canvas, and the golden was
//    green over it for as long as it existed.
// 3. A chart drawn in Typst inherits the document's fonts, colours and type scale.
//    An SVG carries its own copy of all three, which is how the palette came to have
//    four values of `accent`.
//
// The geometry arrives pre-computed as fractions of the plot box, because the axis and
// tick arithmetic belongs where it can be unit-tested. These functions place; they do
// not decide.

#import "_design.typ": accent, ink, mist, rule, slate

// `curve` needs concrete lengths, so the width is read from the container with `layout`
// rather than hardcoded. Hardcoding it meant the plot filled 452pt of a 727pt card and
// sat marooned against the left edge; and a chart that only fits one container is not a
// primitive other families can reuse (#160).
//
// This is not self-referential -- the width comes from the container and the height is
// fixed -- so it converges inside Typst's five layout passes.
#let PLOT_HEIGHT = 132pt
#let AXIS_GUTTER = 30pt
#let LABEL_BAND = 16pt

#let _plot-x(fraction, width) = fraction * width
#let _plot-y(fraction, height) = fraction * height

// One series drawn as a line with a marker at each observation.
#let _series-path(points, width, height, paint, dash: none) = {
  if points.len() == 0 { return }
  curve(
    stroke: (paint: paint, thickness: 1.6pt, cap: "round", join: "round", dash: dash),
    curve.move((_plot-x(points.at(0).at, width), _plot-y(points.at(0).value, height))),
    ..points.slice(1).map(point =>
      curve.line((_plot-x(point.at, width), _plot-y(point.value, height)))
    ),
  )
}

#let _series-markers(points, width, height, paint) = {
  for point in points {
    place(
      top + left,
      dx: _plot-x(point.at, width) - 2.6pt,
      dy: _plot-y(point.value, height) - 2.6pt,
      circle(radius: 2.6pt, fill: white, stroke: 1.4pt + paint),
    )
  }
}

// `gridlines` and `points` carry fractions of the plot box, already clamped to it by the
// caller. `at` runs left to right, `value` runs top to bottom, both in [0, 1].
#let _legend(series-label, benchmark-label) = text(size: 6.8pt, fill: ink)[
  #box(baseline: -0.5pt, circle(radius: 2.4pt, fill: white, stroke: 1.4pt + accent))
  #h(3pt)#series-label
  #if benchmark-label != none [
    #h(10pt)#box(
      baseline: -1pt,
      line(length: 10pt, stroke: (paint: slate, thickness: 1.4pt, dash: "dashed")),
    )
    #h(3pt)#benchmark-label
  ]
]

#let line-chart(
  gridlines: (),
  points: (),
  labels: (),
  benchmark: (),
  benchmark-label: none,
  series-label: "Portfolio",
  height: PLOT_HEIGHT,
) = layout(available => {
  let width = available.width - AXIS_GUTTER
  block(width: 100%, height: height + LABEL_BAND + 14pt)[
    #place(top + right, dy: 0pt, _legend(series-label, benchmark-label))
    #place(top + left, dx: AXIS_GUTTER, dy: 14pt)[
      #block(width: width, height: height)[
        #for gridline in gridlines [
          #place(
            top + left,
            dy: _plot-y(gridline.at, height),
            line(
              length: width,
              // The zero line is the one a reader looks for, so it is drawn darker.
              stroke: (paint: if gridline.zero { slate } else { rule }, thickness: 0.5pt),
            ),
          )
          #place(
            top + left,
            dx: -AXIS_GUTTER,
            dy: _plot-y(gridline.at, height) - 4pt,
            box(width: AXIS_GUTTER - 5pt)[
              #align(right)[#text(size: 6.1pt, fill: slate)[#gridline.label]]
            ],
          )
        ]
        #_series-path(benchmark, width, height, slate, dash: "dashed")
        #_series-path(points, width, height, accent)
        #_series-markers(points, width, height, accent)
      ]
    ]
    #for label in labels [
      #place(
        top + left,
        dx: AXIS_GUTTER + _plot-x(label.at, width) - 16pt,
        dy: height + 18pt,
        box(width: 32pt)[#align(center)[#text(size: 6.1pt, fill: slate)[#label.text]]],
      )
    ]
  ]
})

// Shown where a chart has no series to draw, so the space says why rather than sitting
// blank -- a blank region reads as a layout fault (#155).
#let chart-empty(message) = block(
  width: 100%,
  height: PLOT_HEIGHT + AXIS_GUTTER,
  fill: mist,
  radius: 2pt,
)[
  #align(center + horizon)[#text(size: 8.1pt, fill: slate)[#message]]
]
