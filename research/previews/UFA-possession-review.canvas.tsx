import { H1, H2, Select, Stack, Table, Text, useHostTheme, useState } from "cursor/canvas";

const DATA = {"game":"2026-04-24-ATL-HTX","url":"https://shownspace.com/game-center/2026-04-24-ATL-HTX","source":"ShownSpace export preserved October 12, 2026; UFA event capture. Checked against live ShownSpace play-by-play November 5, 2026.","rawSha256":"78987b3d01b327e1df4d65fd7d9dc346f6376e493eb4a568c5d88681eadcd4f8","selection":"Purposive examples for interpretation, not a representative sample or a test of team tendencies.","cases":[{"id":"A","title":"Opening pass toward the middle","team":"Atlanta Hustle","quarter":1,"point":3,"ownPossession":1,"sourceSide":"away","pointStartIndex":7,"start":"In-bounds pull","prompt":"Your review: throw 1 is setup; throw 2 starts the attack. Both throws remain in the full-possession count.","sourceCue":"Q1 \u00b7 1\u20131 \u00b7 Possession 1 \u00b7 5 plays","throws":[{"n":1,"from":"Ryan Flick","to":"Austin Taylor","xy":[-17.74,18.81,-3.01,17.38],"outcome":"Complete","huck":false,"sourceIndex":8,"before":[]},{"n":2,"from":"Austin Taylor","to":"Brett Hulsmeyer","xy":[-3.01,17.38,6.88,86.72],"outcome":"Complete","huck":true,"sourceIndex":9,"before":[]},{"n":3,"from":"Brett Hulsmeyer","to":"Hayden Austin-Knab","xy":[6.88,86.72,19.98,87.61],"outcome":"Complete","huck":false,"sourceIndex":10,"before":[]},{"n":4,"from":"Hayden Austin-Knab","to":"Brett Hulsmeyer","xy":[19.98,87.61,8.66,86.79],"outcome":"Complete","huck":false,"sourceIndex":11,"before":[]},{"n":5,"from":"Brett Hulsmeyer","to":"Austin Taylor","xy":[8.66,86.79,14.45,103.77],"outcome":"Goal","huck":false,"sourceIndex":12,"before":[]}],"userReview":{"reviewer":"Teddy","date":"2026-11-05","setupThrow":1,"firstAttackingThrow":2,"basis":"User interpretation of this recorded example; not film-validated or applied to other possessions."}},{"id":"B","title":"Opening from the brick location","team":"Atlanta Hustle","quarter":3,"point":1,"ownPossession":1,"sourceSide":"away","pointStartIndex":188,"start":"Out-of-bounds pull; first throw at (0, 40)","prompt":"Here the disc starts at the brick location, with no earlier centering pass.","sourceCue":"Q3 \u00b7 9\u201317 \u00b7 Possession 1 \u00b7 3 plays","throws":[{"n":1,"from":"Austin Taylor","to":"Ryan Flick","xy":[0,40,-9.83,38.79],"outcome":"Complete","huck":false,"sourceIndex":189,"before":[]},{"n":2,"from":"Ryan Flick","to":"Hayden Austin-Knab","xy":[-9.83,48.79,-11.26,62.24],"outcome":"Complete","huck":false,"sourceIndex":191,"before":[17]},{"n":3,"from":"Hayden Austin-Knab","to":"Alec Wilson Holliday","xy":[-11.26,62.24,-2.12,115.15],"outcome":"Goal","huck":true,"sourceIndex":192,"before":[]}]},{"id":"C","title":"Later inward pass, not a centering pass","team":"Atlanta Hustle","quarter":1,"point":5,"ownPossession":1,"sourceSide":"away","pointStartIndex":16,"start":"In-bounds pull","prompt":"Your review: this is not a centering pass. Moving inward after two upfield passes does not make it an opening setup pass.","sourceCue":"Q1 \u00b7 2\u20132 \u00b7 Possession 1 \u00b7 7 plays","throws":[{"n":1,"from":"Hayden Austin-Knab","to":"Ryan Flick","xy":[-12.21,17.25,-15.42,29.11],"outcome":"Complete","huck":false,"sourceIndex":17,"before":[]},{"n":2,"from":"Ryan Flick","to":"Sean Connole","xy":[-15.42,29.11,-18.28,41.79],"outcome":"Complete","huck":false,"sourceIndex":18,"before":[]},{"n":3,"from":"Sean Connole","to":"Ryan Flick","xy":[-18.28,41.79,-4.1,36.47],"outcome":"Complete","huck":false,"sourceIndex":19,"before":[]},{"n":4,"from":"Ryan Flick","to":"Hayden Austin-Knab","xy":[-4.1,36.47,5.59,35.31],"outcome":"Complete","huck":false,"sourceIndex":20,"before":[]},{"n":5,"from":"Hayden Austin-Knab","to":"Jeremy Langdon","xy":[5.59,35.31,9,39.54],"outcome":"Complete","huck":false,"sourceIndex":21,"before":[]},{"n":6,"from":"Jeremy Langdon","to":"Sean Connole","xy":[9,39.54,13.57,48.47],"outcome":"Complete","huck":false,"sourceIndex":22,"before":[]},{"n":7,"from":"Sean Connole","to":"Austin Taylor","xy":[13.57,48.47,-9.83,110.45],"outcome":"Goal","huck":true,"sourceIndex":23,"before":[]}],"userReview":{"reviewer":"Teddy","date":"2026-11-05","centering":false,"decision":"The example is not a centering pass; moving inward is insufficient to label centering."}},{"id":"D","title":"Houston before losing the disc","team":"Houston Havoc","quarter":3,"point":5,"ownPossession":1,"sourceSide":"home","pointStartIndex":221,"start":"In-bounds pull","prompt":"Your review: throw 1 is a centering pass. Houston then continues to 13 throws before turning the disc over. Compare with E.","sourceCue":"Q3 \u00b7 9\u201321 \u00b7 Possession 1 \u00b7 13 plays","throws":[{"n":1,"from":"Mark Turner","to":"Jimmy Zuraw","xy":[-12.59,2.45,-1.14,14.72],"outcome":"Complete","huck":false,"sourceIndex":222,"before":[]},{"n":2,"from":"Jimmy Zuraw","to":"Mark Baldauf","xy":[-1.14,14.72,12.22,15.45],"outcome":"Complete","huck":false,"sourceIndex":223,"before":[]},{"n":3,"from":"Mark Baldauf","to":"Jimmy Zuraw","xy":[12.22,15.45,-4.23,9.54],"outcome":"Complete","huck":false,"sourceIndex":224,"before":[]},{"n":4,"from":"Jimmy Zuraw","to":"Mark Turner","xy":[-4.23,9.54,-16.22,17.18],"outcome":"Complete","huck":false,"sourceIndex":225,"before":[]},{"n":5,"from":"Mark Turner","to":"Mark Baldauf","xy":[-16.22,17.18,-0.05,8.54],"outcome":"Complete","huck":false,"sourceIndex":226,"before":[]},{"n":6,"from":"Mark Baldauf","to":"Mark Turner","xy":[-0.05,8.54,-14.5,13.18],"outcome":"Complete","huck":false,"sourceIndex":227,"before":[]},{"n":7,"from":"Mark Turner","to":"Noah Furrh","xy":[-14.5,13.18,2.13,16.63],"outcome":"Complete","huck":false,"sourceIndex":228,"before":[]},{"n":8,"from":"Noah Furrh","to":"Emmanuel Bilolo","xy":[2.13,16.63,-23.4,26.36],"outcome":"Complete","huck":false,"sourceIndex":229,"before":[]},{"n":9,"from":"Emmanuel Bilolo","to":"Mark Turner","xy":[-23.4,26.36,-15.31,11],"outcome":"Complete","huck":false,"sourceIndex":230,"before":[]},{"n":10,"from":"Mark Turner","to":"Mark Baldauf","xy":[-15.31,11,-21.49,34.45],"outcome":"Complete","huck":false,"sourceIndex":231,"before":[]},{"n":11,"from":"Mark Baldauf","to":"Emmanuel Bilolo","xy":[-21.49,44.45,-15.77,54.45],"outcome":"Complete","huck":false,"sourceIndex":233,"before":[17]},{"n":12,"from":"Emmanuel Bilolo","to":"Noah Furrh","xy":[-15.77,54.45,-21.95,62.81],"outcome":"Complete","huck":false,"sourceIndex":234,"before":[]},{"n":13,"from":"Noah Furrh","to":"Unrecorded target","xy":[-21.95,62.81,-5.87,64],"outcome":"Throwaway","huck":false,"sourceIndex":235,"before":[]}],"userReview":{"reviewer":"Teddy","date":"2026-11-05","centering":true,"decision":"The first throw is a centering pass. All 13 physical throws remain in the possession count."}},{"id":"E","title":"Houston after regaining the disc","team":"Houston Havoc","quarter":3,"point":5,"ownPossession":2,"sourceSide":"home","pointStartIndex":221,"start":"Regain after an opponent turnover","prompt":"Your review: this is not a centering pass. The first throw is a completed huck; the possession ends in a turnover on throw 3.","sourceCue":"Q3 \u00b7 9\u201321 \u00b7 Possession 3 \u00b7 3 plays","throws":[{"n":1,"from":"Jimmy Zuraw","to":"Brian Gfroerer","xy":[10.22,21,18.3,76.09],"outcome":"Complete","huck":true,"sourceIndex":237,"before":[17]},{"n":2,"from":"Brian Gfroerer","to":"Mark Baldauf","xy":[18.3,76.09,19.94,63.81],"outcome":"Complete","huck":false,"sourceIndex":238,"before":[]},{"n":3,"from":"Mark Baldauf","to":"Mark Turner","xy":[19.94,63.81,16.3,53.09],"outcome":"Drop","huck":false,"sourceIndex":239,"before":[]}],"userReview":{"reviewer":"Teddy","date":"2026-11-05","centering":false,"decision":"The first throw is not a centering pass; it is a huck."}}]};

export default function PossessionReview() {
  const theme = useHostTheme();
  const [caseId, setCaseId] = useState("A");
  const [focus, setFocus] = useState("1");
  const item = DATA.cases.find(c => c.id === caseId) || DATA.cases[0];
  const selected = item.throws.find(t => String(t.n) === focus);
  const sx = (x: number) => 60 + (x + 26.6667) * 5;
  const sy = (y: number) => 650 - y * 5;
  const border = theme.stroke.tertiary;
  const muted = theme.text.secondary;
  const accent = theme.accent.primary;
  const important = selected || item.throws[0];
  const outcome = item.throws[item.throws.length - 1].outcome;
  const penalties = item.throws.filter(t => t.before.includes(16) || t.before.includes(17));
  function arrow(t: typeof item.throws[number]) {
    const [tx, ty, rx, ry] = t.xy;
    const a = [sx(tx), sy(ty)], b = [sx(rx), sy(ry)];
    const angle = Math.atan2(b[1] - a[1], b[0] - a[0]);
    const head = [b, [b[0] - 10 * Math.cos(angle - 0.45), b[1] - 10 * Math.sin(angle - 0.45)], [b[0] - 10 * Math.cos(angle + 0.45), b[1] - 10 * Math.sin(angle + 0.45)]];
    const active = !selected || selected.n === t.n;
    const color = active ? accent : muted;
    return <g key={t.n} opacity={active ? 1 : 0.23} data-throw-number={t.n}>
      <title>{`Throw ${t.n}: ${t.from} → ${t.to}. ${t.outcome}${t.huck ? ", huck" : ""}.`}</title>
      <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={color} strokeWidth={active ? 3 : 1.5} strokeDasharray={t.outcome === "Throwaway" || t.outcome === "Drop" || t.outcome === "Callahan" ? "7 4" : undefined}/>
      <polygon points={head.map(p => p.join(",")).join(" ")} fill={color}/>
      <circle cx={a[0]} cy={a[1]} r={3} fill={color}/>
      {active && <text x={a[0] + 7} y={a[1] - 7} fill={theme.text.primary} fontSize={14} fontWeight={600}>{t.n}</text>}
    </g>;
  }
  return <Stack gap={14}>
    <H1>Review these possessions</H1>
    <Text>Atlanta at Houston · April 24, 2026. Five selected examples to discuss opening passes and play after regaining the disc.</Text>
    <label style={{display:"grid", gap:6}}>
      <span style={{color:muted, fontSize:13}}>Choose a recorded possession</span>
      <Select value={caseId} onChange={value => {setCaseId(value); setFocus("1");}} options={DATA.cases.map(c => ({value:c.id, label:c.id + " · " + c.title}))}/>
    </label>
    <H2>{item.id} · {item.title}</H2>
    <Text>{item.team} · Q{item.quarter}, point {item.point} · Team possession {item.ownPossession} · {item.throws.length} throws · Ends in {outcome.toLowerCase()}</Text>
    <Text size="small" tone="secondary">{item.start}. Every recorded physical throw is retained; no centering pass has been removed.</Text>
    <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(min(100%, 320px), 1fr))", gap:24, alignItems:"start"}}>
      <section>
        <label style={{display:"grid", gap:6}}>
          <span style={{color:muted, fontSize:13}}>Highlight a throw</span>
          <Select value={focus} onChange={setFocus} options={[{value:"all",label:"All throws"}, ...item.throws.map(t => ({value:String(t.n),label:`Throw ${t.n} · ${t.outcome}${t.huck ? " · Huck" : ""}`}))]}/>
        </label>
        <svg viewBox="0 0 390 710" style={{width:"100%",maxHeight:590}} role="img" aria-label={`Recorded throwing locations for case ${item.id}. Attacking upward. Horizontal coordinates are yards from the centerline; vertical coordinates are yards from the back of the defended end zone.`}>
          <title>Recorded throw locations · {item.team} · Q{item.quarter}, point {item.point}</title>
          <rect x={60} y={50} width={266.667} height={600} fill="none" stroke={muted}/>
          <rect x={60} y={50} width={266.667} height={100} fill={accent} opacity={0.06}/>
          <rect x={60} y={550} width={266.667} height={100} fill={accent} opacity={0.06}/>
          {[0,20,40,60,80,100,120].map(y => <g key={y}>
            <line x1={60} x2={326.667} y1={sy(y)} y2={sy(y)} stroke={y === 20 || y === 100 ? muted : border}/>
            <text x={49} y={sy(y)+5} textAnchor="end" fontSize={13} fill={muted}>{y}</text>
          </g>)}
          <line x1={sx(0)} x2={sx(0)} y1={50} y2={650} stroke={border} strokeDasharray="4 5"/>
          <text x={193} y={24} textAnchor="middle" fill={theme.text.primary} fontSize={14}>Attack ↑ · goal line at 100 yd</text>
          <text transform="translate(15 350) rotate(-90)" textAnchor="middle" fontSize={12} fill={muted}>Yards from defended back line</text>
          <text x={193} y={700} textAnchor="middle" fontSize={12} fill={muted}>Yards from centerline</text>
          {[-20,0,20].map(x => <text key={x} x={sx(x)} y={674} textAnchor="middle" fill={muted} fontSize={13}>{x}</text>)}
          {item.id === "B" && <g>
            <circle cx={sx(0)} cy={sy(40)} r={6} fill="none" stroke={muted}/>
            <text x={sx(0)+10} y={sy(40)+18} fill={muted} fontSize={12}>Brick location</text>
          </g>}
          {item.throws.filter(t => !selected || t.n !== selected.n).map(arrow)}
          {selected && arrow(selected)}
        </svg>
        <Text size="small" tone="secondary">Solid: completed pass. Dashed: incomplete attempt. Arrows connect recorded start and endpoint; they do not show flight paths or player movement.</Text>
      </section>
      <section>
        <Text weight="semibold">{item.prompt}</Text>
        <Text>{selected ? `Throw ${selected.n}: ${selected.from} → ${selected.to}. ${selected.outcome}${selected.huck ? " · Huck" : ""}.` : "All recorded throws are shown."}</Text>
        <Table headers={["Throw","Thrower → receiver / target","Result"]} rows={item.throws.map(t => [String(t.n),t.from + " → " + t.to,t.outcome + (t.huck ? " · Huck" : "")])} columnAlign={["right","left","left"]}/>
        {penalties.length > 0 && <Text size="small" tone="secondary">Recorded penalty before throw{penalties.length > 1 ? "s" : ""} {penalties.map(t => t.n).join(", ")}. Any awarded movement is not counted as a throw.</Text>}
        <Text size="small" tone="secondary">ShownSpace locator: Play-by-Play → {item.sourceCue}. The site's possession numbering includes both teams; our team possession number counts only the receiving team's turns with the disc.</Text>
        <a href={DATA.url} target="_blank" rel="noreferrer" style={{color:theme.text.link}}>Open the original game in ShownSpace</a>
      </section>
    </div>
    <details style={{borderTop:"1px solid " + border,paddingTop:12}}>
      <summary style={{cursor:"pointer",color:muted}}>Sources and limits</summary>
      <Text size="small">{DATA.source}</Text>
      <Text size="small">{DATA.selection}</Text>
      <Text size="small">Huck labels use the existing study rule: more than 40 yards in straight-line distance and more than 30 yards toward the attacking end zone. These labels do not establish throw difficulty or receiver openness.</Text>
      <Text size="small">A brick location plus an out-of-bounds pull is compatible with a brick restart; the raw record has no explicit brick-choice field. An in-bounds flag does not identify whether the pull was caught or picked up.</Text>
      <Text size="small">Source event indices ({item.sourceSide}): {item.throws.map(t => t.sourceIndex).join(", ")}. Point-start index: {item.pointStartIndex}. These are data-based reconstructions, not film-reviewed tactical labels.</Text>
    </details>
  </Stack>;
}
