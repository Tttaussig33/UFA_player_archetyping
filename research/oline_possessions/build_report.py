"""Refresh the existing self-contained report from reviewed aggregate results."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
CANVAS = Path('/Users/teddytaussig/.cursor/projects/Users-teddytaussig-Desktop-Work-UFA-player-archetyping/canvases/UFA-oline-regain-hucking.canvas.tsx')

BODY = r'''
type Estimate = {stage:number; estimate:number|null; n?:number; sum?:number; ci95:[number,number]|null};
const names = ["First", "Second", "Third or later"];
const pct = (v:number) => (100*v).toFixed(1)+"%";
const number = (v:number) => v.toLocaleString();
const signed = (v:number) => (v>0?"+":"")+v.toFixed(1);
const range = (v:number[], scale=1) => v.map(x=>(scale*x).toFixed(1)).join(" to ");
const SOURCE = "Source: preserved ShownSpace export and UFA event sequences · 2026 regular season · analysis November 5, 2026.";
const metrics:Record<string,{label:string;unit:string;count:boolean;denominator:string;explain:string}> = {
  early_huck:{label:"Huck in the first 3 throws",unit:"% of eligible possessions",count:false,denominator:"possessions",explain:"The share of possessions with at least one huck in their first three actual throws. Retains possessions that end before throw three. Starts must be at least 40 yards from the attacking goal line."},
  throws_goal:{label:"Throws before a goal",unit:"mean throws per goal possession",count:true,denominator:"goal possessions",explain:"The average number of physical throws in possessions that end in a goal. Every actual throw counts, including setup passes. All starting locations are included."},
  throws_turnover:{label:"Throws before a turnover",unit:"mean throws per turnover possession",count:true,denominator:"turnover possessions",explain:"The average number of physical throws in possessions that end in a turnover, including the final incomplete throw. A stall adds no physical throw. All starting locations are included."},
  scoring:{label:"Possession scoring rate",unit:"% of resolved possessions",count:false,denominator:"resolved possessions",explain:"Goals divided by possessions ending in a goal or turnover. Period-ending possessions are listed separately. Near-goal starts remain included."},
  huck_share:{label:"Hucks as a share of throws",unit:"% of physical throws",count:false,denominator:"throws",explain:"Huck attempts divided by all actual throws in eligible possessions. A shorter possession can have a higher huck share without being more likely to contain a huck."},
  any_huck:{label:"Any huck during the possession",unit:"% of eligible possessions",count:false,denominator:"possessions",explain:"The share of eligible possessions containing at least one huck, regardless of which throw it occurs on. Each possession counts once."},
  huck_completion:{label:"Actual huck catch rate",unit:"% of huck attempts",count:false,denominator:"huck attempts",explain:"Completed hucks divided by attempts, with drops counted as incomplete. The team comparison is descriptive and unadjusted; small regained-huck samples limit conclusions about accuracy."}
};
function chartValue(g:Estimate, count=false) { return Number(((g.estimate||0)*(count?1:100)).toFixed(1)); }
function groupText(g:Estimate, count=false) { return !g || !g.n || g.estimate==null ? "— (0)" : (count?g.estimate.toFixed(1):pct(g.estimate))+" ("+number(g.n)+")"; }
function Counts({groups,count=false,denominator="possessions"}:{groups:Estimate[];count?:boolean;denominator?:string}) {
  return <Table headers={["Team possession","Observed result","95% uncertainty range","Number of "+denominator]}
    rows={groups.map(g=>[names[g.stage-1],g.estimate==null?"—":(count?g.estimate.toFixed(2):pct(g.estimate)),g.ci95?range(g.ci95,count?1:100)+(count?" throws":"% "):"—",number(g.n||0)])}
    columnAlign={["left","right","right","right"]}/>;
}
function SingleChart({groups,label,count=false,max}:{groups:Estimate[];label:string;count?:boolean;max?:number}) {
  const visible=groups.filter(g=>g.estimate!=null && (g.n===undefined || g.n>0));
  return <BarChart categories={visible.map(g=>names[g.stage-1])}
    series={[{name:label,data:visible.map(g=>chartValue(g,count)),tone:"info"}]}
    height={245} showValues beginAtZero yMax={max} valueSuffix={count?"":"%"}/>;
}

export default function OLineRegainHucking() {
  const theme=useHostTheme();
  const [metric,setMetric]=useState("early_huck");
  const [teamId,setTeamId]=useState("hustle");
  const [scoringView,setScoringView]=useState("observed");
  const teams=[...DATA.teams].sort((a:any,b:any)=>a.team_name.localeCompare(b.team_name));
  const team=teams.find((t:any)=>t.team===teamId)||teams[0];
  const spec=metrics[metric];
  const modeled=metric!=="huck_completion";
  const catchComparison=team.metrics.huck_completion.first_vs_all_subsequent;
  const change=modeled?DATA.team_changes[metric].teams.find((t:any)=>t.team===team.team):{...catchComparison.differences[0],subsequent_n:catchComparison.groups[1].n,games:catchComparison.games};
  const early=DATA.league.early_huck.groups;
  const caught=DATA.league.huck_completion.groups;
  const rawScore=DATA.league.scoring.groups;
  const scoreGroups=scoringView==="observed"?rawScore:DATA.adjusted.scoring.groups;
  const sectionStyle={paddingTop:24,borderTop:`1px solid ${theme.stroke.tertiary}`};
  const linkStyle={color:theme.text.link};
  return <Stack gap={28} style={{padding:22,maxWidth:1100,margin:"0 auto",color:theme.text.primary}}>
    <Stack gap={10}>
      <H1>How O-lines change after regaining possession</H1>
      <Text>2026 UFA regular season · 22 teams · 131 of 132 games · exploratory research</Text>
      <Text><strong>The clearest change is earlier hucking and fewer throws.</strong> On a team's second possession, a huck appears in the first three throws more often than on its first possession. Fewer throws remain apparent after accounting for starting location. Scoring does not clearly fall after a regain.</Text>
      <Text tone="secondary">This compares subsequent possessions within the same receiving point. It does not compare one point with the next, and it does not restrict the sample to eventual holds.</Text>
      <div style={{display:"flex",gap:18,flexWrap:"wrap",fontSize:14}}>
        <a href="#league" style={linkStyle}>League results</a><a href="#teams" style={linkStyle}>Compare teams</a><a href="#huck-outcomes" style={linkStyle}>Huck outcomes</a><a href="#paper" style={linkStyle}>Research direction</a><a href="#methods" style={linkStyle}>Definitions and checks</a>
      </div>
    </Stack>
    <section aria-label="How to read the comparisons">
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,230px),1fr))",gap:20}}>
        <Text><strong>First</strong><br/>The receiving team's opening possession after the pull.</Text>
        <Text><strong>Second</strong><br/>Its first possession after losing the disc and getting it back.</Text>
        <Text><strong>Third or later</strong><br/>Its possessions after further losses and recoveries within that point.</Text>
      </div>
      <Text size="small" tone="secondary" style={{marginTop:16}}>All physical throws are retained. Possessions containing a recorded timeout are excluded without changing their original numbers. Huck comparisons omit starts less than 40 yards from the attacking goal line; scoring and throw counts retain them.</Text>
    </section>

    <section id="league" style={sectionStyle}>
      <Stack gap={12}>
        <H2>1. Hucks come earlier after a regain</H2>
        <Text>A huck occurs in the first three throws in <strong>{pct(early[0].estimate)}</strong> of first possessions, <strong>{pct(early[1].estimate)}</strong> of second possessions, and <strong>{pct(early[2].estimate)}</strong> of third-or-later possessions.</Text>
        <Text size="small">Horizontal: team possession within the point. Vertical: percentage of eligible possessions with a huck in their first three throws.</Text>
        <SingleChart groups={early} label="Huck within first 3 throws" max={30}/>
        <Text>For example, 20.9% means about 21 out of 100 eligible second possessions contain an early huck. The adjusted first-to-second increase is <strong>{signed(100*DATA.adjusted.early_huck.differences[0].difference)} percentage points</strong> (95% range {range(DATA.adjusted.early_huck.differences[0].ci95,100)}).</Text>
        <Text>However, the share with a huck anywhere in the possession is almost unchanged: {pct(DATA.league.any_huck.groups[0].estimate)} first versus {pct(DATA.league.any_huck.groups[1].estimate)} second. The evidence points to a shift toward the beginning of a possession, rather than simply more possessions containing hucks.</Text>
        <Text size="small" tone="secondary">{SOURCE} First: {number(early[0].sum)} / {number(early[0].n)}; second: {number(early[1].sum)} / {number(early[1].n)}; third or later: {number(early[2].sum)} / {number(early[2].n)}. Third-or-later evidence is less precise.</Text>
        <details><summary>Counts, uncertainty, and the opening centering pass</summary><Stack gap={12} style={{marginTop:14}}>
          <Counts groups={early}/>
          <Text>The first pass can be setup after a pull. The huck share also rises on throws 2–3: {pct(DATA.throw_windows[1].groups[0].estimate)} first versus {pct(DATA.throw_windows[1].groups[1].estimate)} second. After context adjustment, that difference is {signed(100*DATA.follow_up_checks.adjusted_huck_choice_throws_2_3.differences[0].difference)} points, with a 95% range of {range(DATA.follow_up_checks.adjusted_huck_choice_throws_2_3.differences[0].ci95,100)}. This smaller, exploratory comparison is less certain than the main first-three-throws result.</Text>
          <Text>Manual review: case A is setup; D is a centering pass; C and E are not centering passes. These examples have been recorded, but they are not enough to classify every opening pass automatically. No blanket first-pass removal is applied.</Text>
          <H2>Huck choices by throw number</H2>
          <Text size="small">Horizontal: actual throw number in the current possession. Vertical: hucks as a percentage of throws in that window. The two series compare first and second possessions.</Text>
          <BarChart categories={DATA.throw_windows.map((w:any)=>w.window)} series={[{name:"First possession",tone:"neutral",data:DATA.throw_windows.map((w:any)=>chartValue(w.groups[0]))},{name:"Second possession",tone:"info",data:DATA.throw_windows.map((w:any)=>chartValue(w.groups[1]))}]} height={260} showValues beginAtZero yMax={12} valueSuffix="%"/>
          <Text size="small" tone="secondary">{SOURCE} A possession must survive long enough to enter a later throw window. This is a per-throw comparison, unlike the per-possession chart above.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section style={sectionStyle}>
      <Stack gap={12}>
        <H2>2. Subsequent possessions use fewer throws</H2>
        <Text>On possessions ending in a goal, the mean falls from <strong>{DATA.league.throws_goal.groups[0].estimate.toFixed(1)} to {DATA.league.throws_goal.groups[1].estimate.toFixed(1)} throws</strong> between first and second possessions. On possessions ending in a turnover, it falls from <strong>{DATA.league.throws_turnover.groups[0].estimate.toFixed(1)} to {DATA.league.throws_turnover.groups[1].estimate.toFixed(1)}</strong>.</Text>
        <Text size="small">Horizontal: team possession within the point. Vertical: mean number of actual throws. The two series separate goal and turnover endings.</Text>
        <BarChart categories={names} series={[{name:"Ends in a goal",tone:"info",data:DATA.league.throws_goal.groups.map((g:Estimate)=>chartValue(g,true))},{name:"Ends in a turnover",tone:"neutral",data:DATA.league.throws_turnover.groups.map((g:Estimate)=>chartValue(g,true))}]} height={275} showValues beginAtZero yMax={12}/>
        <Text>Regained possessions begin about 24 yards farther upfield on average, which explains part of the difference. After accounting for starting location and other recorded context, second possessions still average <strong>{Math.abs(DATA.adjusted.throws_goal.differences[0].difference).toFixed(1)} fewer throws before goals</strong> and <strong>{Math.abs(DATA.adjusted.throws_turnover.differences[0].difference).toFixed(1)} fewer before turnovers</strong>.</Text>
        <Text>These are fewer passing actions within a possession. That fits the change in approach you described. The analysis does not attribute the entire difference to hucks or establish what players were feeling.</Text>
        <Text size="small" tone="secondary">{SOURCE} All field locations; goals and turnovers shown separately. Completed hucks can shorten the passing sequence, but possession length and huck choice are not independent measures.</Text>
        <details><summary>Throw-count denominators and uncertainty</summary><Stack gap={12} style={{marginTop:14}}>
          <Text weight="semibold">Possessions ending in a goal</Text><Counts groups={DATA.league.throws_goal.groups} count denominator="goal possessions"/>
          <Text weight="semibold">Possessions ending in a turnover</Text><Counts groups={DATA.league.throws_turnover.groups} count denominator="turnover possessions"/>
          <Text size="small">The final incomplete throw counts. Stalls add no throw; Callahan catches can create a zero-throw goal possession. Those outcomes are retained in the raw totals. Period-ending possessions are not included in either mean.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section style={sectionStyle}>
      <Stack gap={12}>
        <H2>3. Scoring does not clearly decrease after a regain</H2>
        <Text>The observed scoring rate is {pct(rawScore[0].estimate)} on first possessions and {pct(rawScore[1].estimate)} on second possessions. But regained possessions often start closer to the goal. Accounting for starting location and game context brings the estimates to roughly 51% for both.</Text>
        <label style={{display:"grid",gap:6,maxWidth:400}}><span>Scoring comparison</span><Select value={scoringView} onChange={setScoringView} options={[{value:"observed",label:"Observed rates — what happened"},{value:"adjusted",label:"Adjusted rates — comparable recorded context"}]}/></label>
        <Text size="small">Horizontal: team possession within the point. Vertical: {scoringView==="observed"?"goals as a percentage of goal-or-turnover possessions":"model-estimated scoring percentage using the same mix of starting locations, teams, opponents, quarters and point-start times"}.</Text>
        <SingleChart groups={scoreGroups} label={scoringView==="observed"?"Observed scoring rate":"Adjusted scoring estimate"} max={100}/>
        <Text>The adjusted first-to-second change is <strong>{signed(100*DATA.adjusted.scoring.differences[0].difference)} percentage points</strong>, with a 95% range from {range(DATA.adjusted.scoring.differences[0].ci95,100)}. The data are compatible with a modest increase or decrease; they do not support your predicted drop in scoring at this stage.</Text>
        <Text size="small" tone="secondary">{SOURCE} Near-goal starts retained. The denominator contains {number(DATA.scope.resolved_possessions)} possessions ending in goals or turnovers. Another {number(DATA.scope.period_end_possessions)} end with the period and are reported separately.</Text>
        <details><summary>Scoring counts and comparisons within similar field areas</summary><Stack gap={12} style={{marginTop:14}}>
          <Counts groups={rawScore} denominator="resolved possessions"/>
          <Text>Each row below compares starts within the same broad area. These are raw within-area rates, not model estimates. Near-goal regains are common and must stay in the scoring analysis.</Text>
          <Table headers={["Yards from starting location to goal line","First: goals / possessions","Second: goals / possessions","Third or later: goals / possessions"]}
            rows={DATA.start_band_rows.map((r:any)=>[r.label,...r.groups.map((g:any)=>g?`${pct(g.rate)} (${g.goals}/${g.n})`:"—")])} columnAlign={["left","right","right","right"]}/>
          <Text size="small">Location is the first recorded throwing or stall location, which may follow movement or a penalty after gaining the disc. Models omit possessions without a known location. The alternate calculation counting period endings as no-goal gives {DATA.sensitivity.period_end_as_no_goal.groups.map((g:Estimate)=>pct(g.estimate||0)).join(", ")} for first, second, and third or later.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="teams" style={sectionStyle}>
      <Stack gap={12}>
        <H2>4. Compare each team with its own opening possession</H2>
        <Text>The strongest evidence of differences across teams is in early hucking after a regain. The overall team-difference test remains detectable after checking six measures. Individual team estimates are less settled: qualifying regain samples can be small, and the table is a starting point for scouting, not a ranking of proven tendencies.</Text>
        <Text>Two contrasting examples: Houston's observed early-huck rate rises from 9.9% (29/294) to 31.3% (20/64) after regains, while Seattle's falls from 14.9% (36/241) to 6.9% (2/29). These combine all subsequent possessions and illustrate different observed patterns; the small samples do not establish lasting team tendencies.</Text>
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,300px),1fr))",gap:18}}>
          <label style={{display:"grid",gap:6}}><span>Measure</span><Select value={metric} onChange={setMetric} options={Object.entries(metrics).map(([value,s])=>({value,label:s.label}))}/></label>
          <label style={{display:"grid",gap:6}}><span>Team</span><Select value={teamId} onChange={setTeamId} options={teams.map((t:any)=>({value:t.team,label:t.team_name}))}/></label>
        </div>
        <H2>{team.team_name}: {spec.label.toLowerCase()}</H2>
        <Text>{spec.explain}</Text>
        <Text size="small">Horizontal: this team's possession within a receiving point. Vertical: {spec.unit}.</Text>
        <div data-selected-team-chart={team.team} data-selected-metric={metric}><SingleChart groups={team.metrics[metric].groups} label={spec.label} count={spec.count} max={spec.count?undefined:metric==="huck_share"?20:metric==="early_huck"?60:100}/></div>
        <Text>{modeled?"Adjusting for recorded context, this":"In the observed catch data, this"} team's change from first to <strong>all subsequent possessions combined</strong> is {signed(change.difference*(spec.count?1:100))} {spec.count?"throws":"percentage points"} (95% range {range(change.ci95,spec.count?1:100)}). That estimate uses {number(change.subsequent_n)} subsequent {spec.denominator} across {change.games} games.</Text>
        <Text size="small" tone="secondary">{SOURCE} Bars are observed values. The change combines second and later possessions to avoid splitting already-small team samples. {modeled?"Within-team adjustment uses each team's recorded context mix.":"Catch differences use whole-game bootstrap ranges; no team-level catch adjustment or ranking is asserted."}</Text>
        <Text weight="semibold">All 22 teams · {spec.label.toLowerCase()}</Text>
        <Text size="small">Each rate or mean is followed by its number of {spec.denominator} in parentheses. The last column compares first with all subsequent possessions {modeled?"after context adjustment":"without adjustment"}; pp means percentage points. A range crossing zero includes no change.</Text>
        <div data-team-table="true"><Table headers={["Team",`First (${spec.count?"mean":"%"}; n)`,`Second (${spec.count?"mean":"%"}; n)`,`Third+ (${spec.count?"mean":"%"}; n)`,`${modeled?"Adjusted":"Observed"} change (${spec.count?"throws":"pp"}); 95% range`]}
          rows={teams.map((t:any)=>{const c=modeled?DATA.team_changes[metric].teams.find((v:any)=>v.team===t.team):t.metrics.huck_completion.first_vs_all_subsequent.differences[0];return [t.team_name+(t.games===11?" *":""),...t.metrics[metric].groups.map((g:Estimate)=>groupText(g,spec.count)),`${signed(c.difference*(spec.count?1:100))} [${range(c.ci95,spec.count?1:100)}]`];})} columnAlign={["left","right","right","right","right"]}/></div>
        <Text size="small" tone="secondary">* Chicago and Pittsburgh have 11 available games; other teams have 12. These 95% ranges are individual intervals, not simultaneous guarantees across all teams. Multiple-comparison corrections are applied to the tests in the methods section; no early-huck team contrast clears the correction across all 132 team-by-measure comparisons.</Text>
      </Stack>
    </section>

    <section id="huck-outcomes" style={sectionStyle}>
      <Stack gap={12}>
        <H2>5. Huck completion is less certain than huck timing</H2>
        <Text>Actual catch rates are {pct(caught[0].estimate)}, {pct(caught[1].estimate)}, and {pct(caught[2].estimate)} across first, second, and third-or-later possessions. The second-possession rate is lower in this sample, but the difference is too uncertain to conclude that regain hucks are less accurate.</Text>
        <Text size="small">Horizontal: team possession within the point. Vertical: completed hucks as a percentage of huck attempts. Drops count as incomplete in this chart.</Text>
        <SingleChart groups={caught} label="Actual huck catch rate" max={100}/>
        <Text>A completed huck also does not have to be an assist to help the possession. Among resolved possessions containing at least one completed huck, {pct(DATA.scoring_after_completed_huck.groups[0].estimate)} of first and {pct(DATA.scoring_after_completed_huck.groups[1].estimate)} of second possessions eventually score. That is a descriptive result conditional on completing a huck; it is not an estimate of how choosing to huck changes scoring probability.</Text>
        <Text size="small" tone="secondary">{SOURCE} Huck attempts: {caught.map((g:Estimate)=>number(g.n||0)).join(" / ")} across the three stages. Third-or-later completion estimates are especially uncertain.</Text>
        <details><summary>Catch counts, drops, and ShownSpace difficulty measures</summary><Stack gap={12} style={{marginTop:14}}>
          <Counts groups={caught} denominator="huck attempts"/>
          <Table headers={["Team possession","Drops / attempts","Mean recorded CP","Drop-credited CPOE"]} rows={DATA.huck_outcomes.map((h:any)=>[names[h.stage-1],`${h.drops} / ${h.attempts}`,pct(h.mean_cp),signed(h.credited_cpoe_pp)+" pp"])} columnAlign={["left","right","right","right"]}/>
          <Text size="small">For this comparison, drop-credited CPOE is recomputed as mean(caught + recorded drop − CP), in percentage points. This follows Braden's explanation that drops are credited for CPOE; it does not reinterpret stored CPOE=1 values. Actual catch rate remains separate. No aEC-per-attempt measure is used.</Text>
          <Text size="small">Recorded CP is used as a fitted difficulty-score covariate in the catch model, rather than assumed perfectly calibrated to actual catches. The adjusted second-minus-first catch difference is {signed(100*DATA.adjusted.huck_completion.differences[0].difference)} pp (95% range {range(DATA.adjusted.huck_completion.differences[0].ci95,100)}). Model identity and production training labels are not independently verified; exclusion of 2026 from CP training remains the agreed working assumption.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="paper" style={sectionStyle}>
      <Stack gap={12}>
        <H2>A clearer research direction</H2>
        <Text><strong>Question:</strong> How does a receiving team's approach change on subsequent possessions within the same point, and how do those changes relate to scoring?</Text>
        <Text><strong>Working finding:</strong> Second possessions involve fewer passing actions and more hucking in the first few throws, even after accounting for recorded field and game context. The evidence does not show a corresponding decrease in possession scoring. Teams differ most clearly in the size of their early-hucking change.</Text>
        <Text><strong>What remains unresolved:</strong> Later regains do not show a clear progressive rise beyond the second possession. Among regained possessions, the number of the receiving team's earlier throws does not clearly predict early hucking. The data support a possession-stage pattern, but do not establish fatigue or impatience as its cause.</Text>
        <Text><strong>Use for coaches:</strong> Compare your team's opening plan with its first few choices after winning the disc back. For an opponent, identify whether giving the disc back tends to be followed by an immediate deep look. Use the team counts to decide which patterns deserve film review, and keep huck timing separate from huck execution and scoring.</Text>
        <details><summary>Check the “long point makes teams antsy” explanation</summary><Stack gap={12} style={{marginTop:14}}>
          <Text>Within subsequent eligible possessions, more prior own-team throws are not clearly associated with early hucking. The adjusted odds ratio for doubling (1 + the prior throw count) is {DATA.prior_activity.prior_own_throws.odds_ratio_for_doubling_one_plus_count.toFixed(2)} (95% range {range(DATA.prior_activity.prior_own_throws.or_ci95)}). A value of 1 means no estimated change in odds.</Text>
          <Table headers={["Earlier own-team throws in the point","Early-huck possessions / eligible regains","Early-huck rate"]} rows={DATA.prior_activity.observed_bands.map((b:any)=>[b.band,`${b.early_hucks} / ${b.n}`,pct(b.rate)])} columnAlign={["left","right","right"]}/>
          <Text size="small">The last band has only 20 possessions. Prior activity means throws before this possession began; it does not use the current possession's eventual length. A separate both-teams activity check is also uncertain and has verified coverage for only {DATA.prior_activity.prior_total_throws.n} of {DATA.prior_activity.prior_total_throws.n+DATA.prior_activity.prior_total_throws.missing} eligible regained possessions.</Text>
        </Stack></details>
      </Stack>
    </section>

    <section id="methods" style={sectionStyle}>
      <details><summary style={{fontSize:19,fontWeight:600}}>Definitions, sensitivity checks, and sources</summary><Stack gap={14} style={{marginTop:16}}>
        <Text><strong>Scope and denominators.</strong> Receiving team is the point-start role, not proof that the same seven players stayed on. Of {number(DATA.audit.source_receiving_points)} raw receiving-point starts, {number(DATA.audit.included_points)} pass sequence checks. These contain {number(DATA.audit.possessions)} possessions before removing {DATA.scope.timeout_possessions_excluded} with timeout markers. After removal, {number(DATA.scope.possessions)} remain. Numbering is preserved. There are 204 third possessions and 43 fourth-or-later possessions before field eligibility; these are grouped because later samples become small.</Text>
        <Text><strong>Huck definition.</strong> More than 40 yards in straight-line distance and more than 30 yards of forward gain. Huck analyses require a first throwing location at least 40 yards from the attacking goal line. This working cutoff keeps comparable room to throw deep; it is not selected to maximize an effect. Scoring and throw-count comparisons retain starts near the end zone.</Text>
        <Text><strong>What adjustment means.</strong> Binomial models estimate scoring and huck probabilities; Poisson mean models estimate throw counts, with uncertainty clustered by game. Starting longitudinal and lateral location, team, opponent, quarter, and the recorded time at the start of the point are included. The latter is not the time at the start of each subsequent possession. Current throwing location is also included in the per-throw huck model. Estimated stages are compared using a common recorded context mix.</Text>
        <Text><strong>Uncertainty and multiple comparisons.</strong> Observed ranges use 10,000 whole-game bootstrap samples. Adjusted ranges use game-cluster covariance; within-team tests use the team's 11–12-game count for a conservative t reference. Holm corrections cover 16 principal league comparisons, six team-difference tests, and all 132 individual team-by-measure contrasts. Ranges and changes matter more than a cutoff: a p-value is not the probability that a hypothesis is true. The early-huck team-difference test has corrected p={DATA.team_changes.early_huck.heterogeneity_p_holm.toFixed(3)}; this does not establish a particular team's rank.</Text>
        <Text><strong>Checks against alternative choices.</strong> The table reports observed first-to-all-subsequent differences. The huck and throw-count direction persists when changing the huck definition, changing the starting-location cutoff, or excluding more potentially disrupted points. The magnitude of huck frequency depends on whether near-goal regains are included.</Text>
        <Table headers={["Alternative analysis","Early huck change (pp)","Huck share change (pp)","Goal-possession throw change"]} rows={DATA.sensitivity_rows.map((r:any)=>[r.label,signed(r.early_huck*100),signed(r.huck_share*100),signed(r.throws_goal)])} columnAlign={["left","right","right","right"]}/>
        <Text size="small">Adjusted scoring remains uncertain when comparing within the same game or restricting scoring to the common starting region. The adjusted shorter-possession and early-hucking differences remain in those checks. Including period endings as no-goal does not reverse the raw scoring pattern. All versions are retained in results.json rather than selecting the most favorable result.</Text>
        <Text><strong>Source limits.</strong> Pittsburgh at Chicago on July 18, 2026 is missing. Twenty-nine receiving points fail sequence/source checks. Four games have at least one raw event stream that disagrees with the final score; valid points are retained, and excluding those games is a sensitivity check. Zero-throw outcomes are retained; unknown starting locations are omitted from location-adjusted models. Setup passes have not been automatically labeled across the league.</Text>
        <Text><strong>Interpretation limits.</strong> Subsequent possessions necessarily follow turnovers and recovery, while the opening baseline includes all receiving points. Restricting opening possessions to points that later regain would select opening failures and invalidate a scoring baseline. Field adjustment reduces measured context differences but cannot account for receiver openness, defensive force, wind, substitutions, or intent. This is an exploratory observational study, not a causal test or a preregistered confirmation.</Text>
        <Text size="small">Sources: local ShownSpace export preserved October 12, 2026, with file hashes checked; archived UFA raw events with capture receipts and hashes; <a href="https://www.docs.ufastats.com/events" style={linkStyle}>UFA event definitions</a>. No live database refresh is claimed. Reproducible cohort, analysis specification, aggregate results, and validation are saved under research/oline_possessions. The earlier unrestricted huck snapshot remains in research/huck_timing_study/oline_regains; its denominators differ from this expanded comparison.</Text>
      </Stack></details>
    </section>
  </Stack>;
}
'''

def main():
    result = json.loads((ROOT/'results.json').read_text())
    result['audit'] = json.loads((ROOT/'cohort_audit.json').read_text())
    labels = {'all_possessions_including_timeouts':'Keep timeout possessions',
      'exclude_whole_timeout_or_injury_points':'Remove whole points with timeouts/injuries',
      'exclude_four_score_discrepancy_games':'Remove four score-discrepancy games',
      'huck_start_y_at_most_50':'Require at least 50 yards to goal',
      'huck_start_y_at_most_70':'Require at least 30 yards to goal',
      'hucks_all_start_locations':'Allow all starting locations',
      'huck_over_40_forward_yards':'Define huck as over 40 forward yards'}
    result['sensitivity_rows']=[{'label':label,**{metric:result['sensitivity'][key][metric]['differences'][0]['difference']
        for metric in ['early_huck','huck_share','throws_goal']}} for key,label in labels.items()]
    bands=[('Own end zone: 0–20','80–100 yd'),('Deep own half: 20–40','60–<80 yd'),
           ('To midfield: 40–60','40–<60 yd'),('Attacking half: 60–80','20–<40 yd'),
           ('Near goal: 80–120','Under 20 yd or in end zone')]
    result['start_band_rows']=[{'label':label,'groups':[next((g for g in result['scoring_by_start']
       if g['band']==band and g['stage']==s),None) for s in [1,2,3]]} for band,label in bands]
    data=json.dumps(result,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    source='import { BarChart, H1, H2, Select, Stack, Table, Text, useHostTheme, useState } from "cursor/canvas";\n\nconst DATA: any = '+data+';\n'+BODY
    CANVAS.write_text(source)
    print(str(CANVAS))

if __name__=='__main__':main()
