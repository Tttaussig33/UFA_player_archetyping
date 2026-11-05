import { BarChart, Grid, H1, H2, Select, Stack, Table, Text, useHostTheme, useState } from "cursor/canvas";

type Player = {name:string; restart_events_including_stalls:number; assists:number; thrower_aec:number; huck_attempts:number; huck_completions:number; huck_drops:number; huck_assists:number};
type Cohort = {summary:Record<string,number>; assist_leaders:Player[]; aec_leaders:Player[]; huck_counts:Player[]};
const DATA:Record<string,Cohort> = {"team_timeout":{"summary":{"candidate_events_before_player_attribution":611,"unattributed_events":0,"restart_events_including_stalls":611,"throws":610,"stalls":1,"players":129,"assists":26,"project_hucks":25,"ufa_documented_hucks":22,"huck_players":22,"max_hucks_one_player":2,"players_at_least_5_hucks":0,"players_at_least_10_hucks":0,"missing_aec":0,"missing_cp_hucks":0},"assist_leaders":[{"name":"Austin Taylor","restart_events_including_stalls":15,"assists":2,"thrower_aec":1.3099195444591405,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Brandon Van Deusen","restart_events_including_stalls":12,"assists":2,"thrower_aec":1.340169479109509,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Elliot Hawkins","restart_events_including_stalls":5,"assists":2,"thrower_aec":1.309533450143687,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0},{"name":"Jordan Kerr","restart_events_including_stalls":11,"assists":2,"thrower_aec":1.585337858573361,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":2},{"name":"Owen Erdman","restart_events_including_stalls":2,"assists":2,"thrower_aec":1.28408834724773,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Ryan Dinger","restart_events_including_stalls":20,"assists":2,"thrower_aec":1.236724820012433,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Ryan Poloz","restart_events_including_stalls":13,"assists":2,"thrower_aec":1.1452829851691637,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0}],"aec_leaders":[{"name":"Spencer Lofink","restart_events_including_stalls":22,"assists":1,"thrower_aec":2.083637560403311,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0},{"name":"Nate Long","restart_events_including_stalls":6,"assists":1,"thrower_aec":2.0558176597412197,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":0},{"name":"Duncan Fitzgerald","restart_events_including_stalls":13,"assists":1,"thrower_aec":1.7591586309673055,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Jordan Kerr","restart_events_including_stalls":11,"assists":2,"thrower_aec":1.585337858573361,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":2},{"name":"Alex Atkins","restart_events_including_stalls":12,"assists":0,"thrower_aec":1.4629874027371568,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":0}],"huck_counts":[{"name":"Alex Atkins","restart_events_including_stalls":12,"assists":0,"thrower_aec":1.4629874027371568,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":0},{"name":"Jordan Kerr","restart_events_including_stalls":11,"assists":2,"thrower_aec":1.585337858573361,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":2},{"name":"Nate Long","restart_events_including_stalls":6,"assists":1,"thrower_aec":2.0558176597412197,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":0}]},"team_timeout_or_injury":{"summary":{"candidate_events_before_player_attribution":852,"unattributed_events":1,"restart_events_including_stalls":851,"throws":850,"stalls":1,"players":230,"assists":41,"project_hucks":30,"ufa_documented_hucks":27,"huck_players":27,"max_hucks_one_player":2,"players_at_least_5_hucks":0,"players_at_least_10_hucks":0,"missing_aec":0,"missing_cp_hucks":0},"assist_leaders":[{"name":"Austin Taylor","restart_events_including_stalls":16,"assists":2,"thrower_aec":1.4716893364277874,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Brandon Van Deusen","restart_events_including_stalls":15,"assists":2,"thrower_aec":1.7879436824480062,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Elliot Hawkins","restart_events_including_stalls":8,"assists":2,"thrower_aec":-0.16209136074424982,"huck_attempts":1,"huck_completions":0,"huck_drops":0,"huck_assists":0},{"name":"Jordan Kerr","restart_events_including_stalls":11,"assists":2,"thrower_aec":1.585337858573361,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":2},{"name":"Owen Erdman","restart_events_including_stalls":2,"assists":2,"thrower_aec":1.28408834724773,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Ryan Dinger","restart_events_including_stalls":20,"assists":2,"thrower_aec":1.236724820012433,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Ryan Poloz","restart_events_including_stalls":13,"assists":2,"thrower_aec":1.1452829851691637,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0},{"name":"Tobe Decraene","restart_events_including_stalls":2,"assists":2,"thrower_aec":0.822142813073244,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0}],"aec_leaders":[{"name":"Spencer Lofink","restart_events_including_stalls":24,"assists":1,"thrower_aec":2.232616808466944,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0},{"name":"Nate Long","restart_events_including_stalls":6,"assists":1,"thrower_aec":2.0558176597412197,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":0},{"name":"Duncan Fitzgerald","restart_events_including_stalls":14,"assists":1,"thrower_aec":1.9173987838779527,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Brandon Van Deusen","restart_events_including_stalls":15,"assists":2,"thrower_aec":1.7879436824480062,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Jordan Kerr","restart_events_including_stalls":11,"assists":2,"thrower_aec":1.585337858573361,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":2}],"huck_counts":[{"name":"Alex Atkins","restart_events_including_stalls":12,"assists":0,"thrower_aec":1.4629874027371568,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":0},{"name":"Jordan Kerr","restart_events_including_stalls":11,"assists":2,"thrower_aec":1.585337858573361,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":2},{"name":"Nate Long","restart_events_including_stalls":6,"assists":1,"thrower_aec":2.0558176597412197,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":0}]},"all_recorded_markers":{"summary":{"candidate_events_before_player_attribution":2378,"unattributed_events":1,"restart_events_including_stalls":2377,"throws":2372,"stalls":5,"players":495,"assists":238,"project_hucks":71,"ufa_documented_hucks":63,"huck_players":59,"max_hucks_one_player":5,"players_at_least_5_hucks":1,"players_at_least_10_hucks":0,"missing_aec":0,"missing_cp_hucks":0},"assist_leaders":[{"name":"Tobe Decraene","restart_events_including_stalls":16,"assists":8,"thrower_aec":2.773227436325643,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0},{"name":"Jordan Kerr","restart_events_including_stalls":17,"assists":5,"thrower_aec":2.9891344418212435,"huck_attempts":3,"huck_completions":3,"huck_drops":0,"huck_assists":3},{"name":"Malik Auger-Semmar","restart_events_including_stalls":20,"assists":5,"thrower_aec":1.341425939194962,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0},{"name":"Alex Atkins","restart_events_including_stalls":26,"assists":4,"thrower_aec":3.3867824623165013,"huck_attempts":5,"huck_completions":4,"huck_drops":1,"huck_assists":2},{"name":"Sean Mott","restart_events_including_stalls":13,"assists":4,"thrower_aec":2.5362971481690364,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0},{"name":"Spencer Lofink","restart_events_including_stalls":38,"assists":4,"thrower_aec":3.4173779607467547,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1}],"aec_leaders":[{"name":"Spencer Lofink","restart_events_including_stalls":38,"assists":4,"thrower_aec":3.4173779607467547,"huck_attempts":1,"huck_completions":1,"huck_drops":0,"huck_assists":1},{"name":"Alex Atkins","restart_events_including_stalls":26,"assists":4,"thrower_aec":3.3867824623165013,"huck_attempts":5,"huck_completions":4,"huck_drops":1,"huck_assists":2},{"name":"Jordan Kerr","restart_events_including_stalls":17,"assists":5,"thrower_aec":2.9891344418212435,"huck_attempts":3,"huck_completions":3,"huck_drops":0,"huck_assists":3},{"name":"Tobe Decraene","restart_events_including_stalls":16,"assists":8,"thrower_aec":2.773227436325643,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0},{"name":"Sean Mott","restart_events_including_stalls":13,"assists":4,"thrower_aec":2.5362971481690364,"huck_attempts":0,"huck_completions":0,"huck_drops":0,"huck_assists":0}],"huck_counts":[{"name":"Alex Atkins","restart_events_including_stalls":26,"assists":4,"thrower_aec":3.3867824623165013,"huck_attempts":5,"huck_completions":4,"huck_drops":1,"huck_assists":2},{"name":"Isaac Lee","restart_events_including_stalls":8,"assists":1,"thrower_aec":1.193288637553261,"huck_attempts":3,"huck_completions":2,"huck_drops":0,"huck_assists":0},{"name":"Jordan Kerr","restart_events_including_stalls":17,"assists":5,"thrower_aec":2.9891344418212435,"huck_attempts":3,"huck_completions":3,"huck_drops":0,"huck_assists":3},{"name":"Chad Yorgason","restart_events_including_stalls":17,"assists":2,"thrower_aec":1.1543359414612606,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":2},{"name":"Mark Baldauf","restart_events_including_stalls":13,"assists":0,"thrower_aec":-0.04494648295204994,"huck_attempts":2,"huck_completions":1,"huck_drops":0,"huck_assists":0},{"name":"Nate Long","restart_events_including_stalls":7,"assists":1,"thrower_aec":1.6389397321509307,"huck_attempts":2,"huck_completions":2,"huck_drops":0,"huck_assists":0},{"name":"Ryan Dinger","restart_events_including_stalls":32,"assists":3,"thrower_aec":0.8978125127066038,"huck_attempts":2,"huck_completions":1,"huck_drops":0,"huck_assists":1}]}};
const OPTIONS = [
 {value:"all_recorded_markers",label:"Timeouts, penalties and injuries — provisional"},
 {value:"team_timeout",label:"Team timeouts only"},
 {value:"team_timeout_or_injury",label:"Team timeouts and injuries"}
];

export default function DeadDiscFirstPass() {
 const theme=useHostTheme();
 const [selected,setSelected]=useState("all_recorded_markers");
 const c=DATA[selected];
 const s=c.summary;
 const selectedLabel=OPTIONS.find(o=>o.value===selected)!.label;
 const provisional=selected==="all_recorded_markers";
 const union=[...new Map([...c.aec_leaders,...c.assist_leaders].map(p=>[p.name,p])).values()]
   .sort((a,b)=>b.thrower_aec-a.thrower_aec||a.name.localeCompare(b.name));
 return <Stack gap={22} style={{padding:22,color:theme.text.primary,maxWidth:1000,margin:"0 auto"}}>
   <Stack gap={8}>
     <H1>UFA throws after recorded stoppage events</H1>
     <Text>2026 regular season · 131 of 132 games · Preliminary observed totals</Text>
     <Text tone="secondary">Study definition: the first throw after a stoppage. Routine turnover fast breaks are separate. These records cover selected event markers, not every dead-disc restart.</Text>
   </Stack>
   <Stack gap={8}>
     <label style={{fontSize:14}}>Included event markers
       <Select value={selected} onChange={setSelected} options={OPTIONS} style={{display:"block",marginTop:8,width:"100%"}} />
     </label>
     <Text weight="semibold">{provisional
       ? "Penalty markers need validation: the feed does not say whether advantage continued or a restart whistle occurred."
       : selected==="team_timeout"
         ? "Explicit team-timeout markers provide the clearest recorded stoppage subset."
         : "Injury timing follows the recorded event order; a whistle timestamp is unavailable."}</Text>
     <Text>{s.restart_events_including_stalls.toLocaleString()} attributed restart events, including {s.stalls} stall{s.stalls===1?"":"s"} · {s.players} players · {s.assists} assists</Text>
     {s.unattributed_events>0 && <Text tone="secondary" size="small">{s.unattributed_events} additional event has no named thrower and is excluded from player totals.</Text>}
   </Stack>
   <Stack gap={8}>
     <H2>Huck ability cannot be ranked reliably from this sample</H2>
     <Text>{s.project_hucks} hucks across {s.huck_players} players; the largest individual sample is {s.max_hucks_one_player}. Completion counts below describe what happened, not a reliable ordering of ability.</Text>
   </Stack>
   <Grid columns="repeat(auto-fit, minmax(min(100%, 440px), 1fr))" gap={26}>
     <Stack gap={8}>
       <H2>Highest observed assist totals</H2>
       <Text size="small" tone="secondary">Players; n = qualifying restart events. Top five including all ties.</Text>
       <BarChart horizontal categories={c.assist_leaders.map(p=>p.name+" (n="+p.restart_events_including_stalls+")")}
         series={[{name:"Assists",data:c.assist_leaders.map(p=>p.assists),tone:"info"}]}
         height={70+42*c.assist_leaders.length} showValues beginAtZero />
       <Text size="small">Horizontal axis: total assists (count)</Text>
       <Text size="small" tone="secondary">{selectedLabel} · 2026, 131 games · ShownSpace throws joined to UFA recorded events.</Text>
     </Stack>
     <Stack gap={8}>
       <H2>Highest observed thrower aEC totals</H2>
       <Text size="small" tone="secondary">Players; n = qualifying restart events. Top five totals.</Text>
       <BarChart horizontal categories={c.aec_leaders.map(p=>p.name+" (n="+p.restart_events_including_stalls+")")}
         series={[{name:"Total thrower aEC",data:c.aec_leaders.map(p=>Number(p.thrower_aec.toFixed(3))),tone:"info"}]}
         height={70+42*c.aec_leaders.length} showValues beginAtZero />
       <Text size="small">Horizontal axis: summed thrower aEC (aEC units)</Text>
       <Text size="small" tone="secondary">{selectedLabel} · 2026, 131 games · Stored aEC with zero thrower credit on drops; stalls included.</Text>
     </Stack>
   </Grid>
   <Stack gap={10}>
     <H2>Observed totals for the players shown above</H2>
     <Text size="small" tone="secondary">Sorted by total thrower aEC. Totals depend on opportunity count, field position and game context.</Text>
     <Table headers={["Player","Restart events","Assists","Total thrower aEC","Hucks completed / attempted"]}
       rows={union.map(p=>[p.name,p.restart_events_including_stalls,p.assists,p.thrower_aec.toFixed(3),p.huck_completions+" / "+p.huck_attempts])}
       columnAlign={["left","right","right","right","right"]} framed={false} />
   </Stack>
   <Stack gap={10}>
     <H2>Players with at least two observed huck attempts</H2>
     <Text size="small" tone="secondary">Sorted by attempts, then name. Actual completions include no credit for drops. Every sample remains too small for a skill ranking.</Text>
     <Table headers={["Player","Attempts","Actual completions","Drops","Huck assists"]}
       rows={c.huck_counts.map(p=>[p.name,p.huck_attempts,p.huck_completions,p.huck_drops,p.huck_assists])}
       columnAlign={["left","right","right","right","right"]} framed={false} />
     <Text size="small" tone="secondary">Huck definition used throughout this project: flight distance over 40 yards and forward gain over 30 yards. The UFA API's documented forward-gain-over-40 definition gives {s.ufa_documented_hucks} hucks in this subset.</Text>
   </Stack>
   <Stack gap={8}>
     <H2>What this covers</H2>
     <Text size="small">First recorded own-team attempt following the selected markers, before any recorded possession, point or period boundary. An event with multiple markers is counted once. A stall before any pass is retained as a restart outcome for contribution totals.</Text>
     <Text size="small">Ordinary out-of-bounds returns, unmarked technical stoppages and restart whistles are not explicitly identified. Penalty-only records are provisional. One regular-season game, Pittsburgh at Chicago on July 18, is absent from the ShownSpace throw data, including the public endpoint rechecked on November 4.</Text>
     <Text size="small">The two source rows that changed between the export and raw-event capture were excluded from matching; neither was a selected restart candidate. One unnamed candidate remains outside player totals. Every displayed total was independently recomputed from original throw rows; Goal-event counting matched 1,152 cached player-game assist totals.</Text>
     <Text size="small">Sources: ShownSpace export dated October 12, 2026; public UFA event arrays captured November 4, 2026. Event codes: 3/5 team timeout, 16/17 penalty, 25 injury, 19 goal.</Text>
     <Text size="small"><a href="https://www.docs.ufastats.com/events" style={{color:theme.text.link}}>UFA event documentation</a> · <a href="https://watchufa.com/sites/default/files/UFA%20Rule%20Book%202026.pdf" style={{color:theme.text.link}}>2026 UFA rules</a></Text>
   </Stack>
 </Stack>;
}
