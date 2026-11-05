/* Portable display adapter for the three UFA reports. No external resources. */
(() => {
  'use strict';
  const SVG = 'http://www.w3.org/2000/svg';
  const svgTags = new Set(['svg', 'g', 'rect', 'line', 'circle', 'text', 'title', 'path', 'polygon', 'polyline', 'ellipse']);
  const unitless = new Set(['opacity', 'fontWeight', 'lineHeight', 'flex', 'flexGrow', 'flexShrink', 'order', 'zIndex']);
  const theme = {
    text: {primary:'var(--report-text)', secondary:'var(--report-muted)', tertiary:'var(--report-muted)', link:'var(--report-accent)'},
    accent: {primary:'var(--report-accent)'},
    stroke: {tertiary:'var(--report-border)'}
  };
  let app, cursor = 0, scheduled = false;
  const states = [], cleanups = [], mounted = [];
  const host = typeof acquireVsCodeApi === 'function' ? acquireVsCodeApi() : null;

  function append(node, children) {
    for (const child of children.flat(Infinity)) {
      if (child == null || typeof child === 'boolean') continue;
      node.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
    }
  }

  function h(tag, props, ...children) {
    props = props || {};
    if (typeof tag === 'function') return tag({...props, children});
    const svg = svgTags.has(tag);
    const el = svg ? document.createElementNS(SVG, tag) : document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (key === 'key' || key === 'children' || value == null) continue;
      if (key === 'style') {
        for (const [name, setting] of Object.entries(value)) {
          el.style[name] = typeof setting === 'number' && !unitless.has(name) ? setting + 'px' : setting;
        }
      } else if (/^on[A-Z]/.test(key)) {
        el.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (key === 'className') {
        el.setAttribute('class', value);
      } else if (typeof value === 'boolean') {
        if (value) el.setAttribute(key, '');
      } else {
        const name = svg && !['viewBox', 'preserveAspectRatio'].includes(key)
          ? key.replace(/[A-Z]/g, c => '-' + c.toLowerCase()) : key;
        el.setAttribute(name, value);
      }
    }
    append(el, children);
    return el;
  }

  const Stack = ({gap = 12, style, children}) => h('div', {className:'ufa-stack', style:{gap, ...style}}, children);
  const Grid = ({columns, gap = 16, style, children}) => h('div', {className:'ufa-grid', style:{gridTemplateColumns:columns, gap, ...style}}, children);
  const H1 = ({children, style}) => h('h1', {style}, children);
  const H2 = ({children, style}) => h('h2', {style}, children);
  const Text = ({children, size, tone, weight, style}) => h('p', {
    className:[size === 'small' ? 'ufa-small' : '', tone === 'secondary' ? 'ufa-secondary' : ''].join(' '),
    style:{...(weight === 'semibold' ? {fontWeight:600} : {}), ...style}
  }, children);

  function Select({value, onChange, options, style}) {
    const select = h('select', {style, onChange:event => onChange(event.target.value)},
      options.map(option => h('option', {value:option.value}, option.label)));
    select.value = value;
    return select;
  }

  function Table({headers, rows, columnAlign = [], striped}) {
    return h('div', {className:'ufa-table-wrap', tabIndex:0, role:'region', 'aria-label':headers.join(', ')},
      h('table', {className:striped ? 'striped' : ''},
        h('thead', {}, h('tr', {}, headers.map((label, i) => h('th', {scope:'col', style:{textAlign:columnAlign[i] || 'left'}}, label)))),
        h('tbody', {}, rows.map(row => h('tr', {}, row.map((cell, i) => h('td', {style:{textAlign:columnAlign[i] || 'left'}}, cell)))))));
  }

  function useState(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial;
    return [states[index], value => {
      states[index] = typeof value === 'function' ? value(states[index]) : value;
      if (!scheduled) {
        scheduled = true;
        queueMicrotask(() => { scheduled = false; paint(); });
      }
    }];
  }

  function BarChart({horizontal = false, categories, series, height = 300, showValues = false, yMax, valueSuffix = ''}) {
    const colors = series.map(s => s.tone === 'neutral' ? 'var(--report-muted)' : 'var(--report-accent)');
    const container = h('div', {className:'ufa-chart'});
    if (series.length > 1) container.appendChild(h('div', {className:'ufa-legend'}, series.map((s, i) =>
      h('span', {}, h('i', {style:{background:colors[i]}}), s.name))));
    const holder = h('div', {});
    container.appendChild(holder);
    const format = value => Number(value.toFixed(3)).toLocaleString() + valueSuffix;

    function draw() {
      const longest = Math.max(...categories.map(c => String(c).length));
      const labelWidth = horizontal ? Math.max(62, longest * 6.7 + 16) : 54;
      const width = Math.max(container.clientWidth, horizontal ? labelWidth + 220 : 550);
      const margin = {left:labelWidth, right:horizontal ? 62 : 20, top:24, bottom:38};
      const innerW = width - margin.left - margin.right;
      const innerH = height - margin.top - margin.bottom;
      const values = series.flatMap(s => s.data);
      const low = Math.min(0, ...values);
      const high = yMax ?? Math.max(1, ...values) * 1.15;
      const range = high - low;
      const x = v => margin.left + (v - low) / range * innerW;
      const y = v => margin.top + (high - v) / range * innerH;
      const svg = h('svg', {width, height, viewBox:`0 0 ${width} ${height}`, role:'img', 'aria-label':series.map(s => s.name).join(' and ')});
      for (let i = 0; i <= 4; i++) {
        const value = low + range * i / 4;
        if (horizontal) {
          svg.appendChild(h('line', {x1:x(value), x2:x(value), y1:margin.top, y2:height - margin.bottom, stroke:'var(--report-border)'}));
          svg.appendChild(h('text', {x:x(value), y:height - 14, textAnchor:'middle'}, format(value)));
        } else {
          svg.appendChild(h('line', {x1:margin.left, x2:width - margin.right, y1:y(value), y2:y(value), stroke:'var(--report-border)'}));
          svg.appendChild(h('text', {x:margin.left - 8, y:y(value) + 4, textAnchor:'end'}, format(value)));
        }
      }
      const stride = (horizontal ? innerH : innerW) / categories.length;
      const barSize = Math.min(horizontal ? 25 : 62, stride * 0.65 / series.length);
      categories.forEach((category, index) => {
        const center = (horizontal ? margin.top : margin.left) + stride * (index + 0.5);
        svg.appendChild(horizontal
          ? h('text', {x:margin.left - 10, y:center + 4, textAnchor:'end'}, category)
          : h('text', {x:center, y:height - 14, textAnchor:'middle'}, category));
        series.forEach((s, j) => {
          const value = Number(s.data[index]);
          const offset = center - (barSize * series.length) / 2 + j * barSize;
          const rect = horizontal
            ? h('rect', {x:Math.min(x(0), x(value)), y:offset, width:Math.abs(x(value) - x(0)), height:barSize - 2, fill:colors[j]})
            : h('rect', {x:offset, y:Math.min(y(0), y(value)), width:barSize - 3, height:Math.abs(y(value) - y(0)), fill:colors[j]});
          rect.setAttribute('data-value', String(value));
          rect.setAttribute('data-category', String(category));
          rect.setAttribute('data-series', s.name);
          rect.appendChild(h('title', {}, `${category} · ${s.name}: ${format(value)}`));
          svg.appendChild(rect);
          if (showValues) svg.appendChild(horizontal
            ? h('text', {x:x(value) + (value >= 0 ? 6 : -6), y:offset + barSize / 2 + 3, textAnchor:value >= 0 ? 'start' : 'end'}, format(value))
            : h('text', {x:offset + (barSize - 3) / 2, y:y(value) - 7, textAnchor:'middle'}, format(value)));
        });
      });
      holder.replaceChildren(svg);
    }
    mounted.push(() => {
      draw();
      const observer = new ResizeObserver(draw);
      observer.observe(container);
      cleanups.push(() => observer.disconnect());
    });
    return container;
  }

  function paint() {
    cleanups.splice(0).forEach(fn => fn());
    cursor = 0;
    const selectedIndex = Array.from(document.querySelectorAll('select')).indexOf(document.activeElement);
    const openDetails = Array.from(document.querySelectorAll('details')).map(el => el.open);
    const root = document.getElementById('ufa-report');
    root.replaceChildren(h(app, {}));
    mounted.splice(0).forEach(fn => fn());
    document.querySelectorAll('details').forEach((el, i) => { if (openDetails[i]) el.open = true; });
    if (selectedIndex >= 0) document.querySelectorAll('select')[selectedIndex]?.focus({preventScroll:true});
    document.title = document.querySelector('h1')?.textContent || document.title;
    host?.postMessage({
      type:'ufa-preview-ready', title:document.title,
      tableRows:Array.from(document.querySelectorAll('tbody')).map(el => el.rows.length),
      chartCount:document.querySelectorAll('svg').length,
      selectors:Array.from(document.querySelectorAll('select')).map(el => el.value)
    });
  }

  window.UFAPreview = {h, Stack, Grid, H1, H2, Text, Select, Table, BarChart,
    useState, useHostTheme:() => theme, render:component => { app = component; paint(); }};
})();
