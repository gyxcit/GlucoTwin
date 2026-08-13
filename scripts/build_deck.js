// Regenere le support de soutenance.  Usage :  node scripts/build_deck.js
// Les figures sont lues dans docs/figures/ ; la sortie va dans docs/.
const pptx = require('pptxgenjs');
const FIG = __dirname + '/../docs/figures/';
const p = new pptx();
p.layout = 'LAYOUT_WIDE';                 // 13.3 x 7.5
p.author = 'Likassi, Djomo, Nze, Ondo, Ndinga';
p.title  = 'GlucoTwin — Accuracy is not enough';

// ---- palette (harmonisee avec les figures du run) ----
const INK='0F1E2E', DEEP='14304A', BLUE='2A78D6', ORANGE='EB6834',
      TEAL='1BAF7A', LIGHT='FFFFFF', WASH='F4F7FA', GREY='5A6B7B', LINE='DDE4EA';
const F='Calibri', FH='Cambria';

const S=()=>p.addSlide();
const dark=s=>s.background={color:INK};
const light=s=>s.background={color:LIGHT};

// bandeau d'auteur discret en bas de slide
function foot(s, who, n){
  s.addText(who, {x:0.55,y:6.92,w:7,h:0.32,fontSize:10,color:GREY,fontFace:F,margin:0});
  s.addText(String(n), {x:12.3,y:6.92,w:0.5,h:0.32,fontSize:10,color:GREY,fontFace:F,align:'right',margin:0});
}
function title(s, t, sub){
  s.addText(t,{x:0.55,y:0.42,w:12.2,h:0.8,fontSize:34,bold:true,color:INK,fontFace:FH,margin:0});
  if(sub) s.addText(sub,{x:0.55,y:1.22,w:12.2,h:0.42,fontSize:15,color:GREY,fontFace:F,margin:0});
}
function card(s,x,y,w,h,fill){
  s.addShape(p.ShapeType.roundRect,{x,y,w,h,rectRadius:0.09,fill:{color:fill||WASH},line:{color:LINE,width:1}});
}
function circleNum(s,x,y,n,col){
  s.addShape(p.ShapeType.ellipse,{x,y,w:0.46,h:0.46,fill:{color:col}});
  s.addText(String(n),{x,y,w:0.46,h:0.46,fontSize:16,bold:true,color:LIGHT,align:'center',valign:'middle',fontFace:F,margin:0});
}

/* ============ 1. TITRE ============ */
{const s=S(); dark(s);
 s.addShape(p.ShapeType.ellipse,{x:10.4,y:-1.5,w:6,h:6,fill:{color:DEEP}});
 s.addShape(p.ShapeType.ellipse,{x:11.6,y:4.4,w:3.4,h:3.4,fill:{color:DEEP}});
 s.addText('GlucoTwin',{x:0.8,y:1.75,w:9,h:1.0,fontSize:54,bold:true,color:LIGHT,fontFace:FH,margin:0});
 s.addText('Accuracy is not enough',{x:0.8,y:2.72,w:9.6,h:0.62,fontSize:26,color:ORANGE,fontFace:FH,italic:true,margin:0});
 s.addText('An interpretable digital twin for type 2 diabetes,\nand an honest look at what glucose forecasting is worth',
   {x:0.8,y:3.5,w:9.2,h:0.95,fontSize:15,color:'AFC3D4',fontFace:F,lineSpacing:22,margin:0});
 s.addShape(p.ShapeType.line,{x:0.85,y:4.72,w:2.0,h:0,line:{color:ORANGE,width:2}});
 s.addText('Regis LIKASSI  ·  Hakim DJOMO  ·  Jean Direl NZE  ·  Xavier ONDO  ·  Seth NDINGA',
   {x:0.8,y:4.95,w:9.6,h:0.34,fontSize:13,color:LIGHT,fontFace:F,margin:0});
 s.addText('AI for Health — PGE5  ·  Prof. Anuradha Kar  ·  September 2026',
   {x:0.8,y:5.35,w:9.6,h:0.34,fontSize:12,color:GREY,fontFace:F,margin:0});
 s.addNotes("REGIS — 20 s\n\nBonjour, nous sommes le groupe qui a travaille sur le Personalized Diabetes Monitoring Twin.\n\nNotre titre annonce la couleur : 'Accuracy is not enough'. Nous allons montrer qu'un jumeau numerique qui optimise son erreur moyenne peut devenir cliniquement inutile — et ce que nous proposons a la place.");
}

/* ============ 2. LE PROBLEME ============ */
{const s=S(); light(s);
 title(s,'Why standard diabetes care falls short','Two structural difficulties that averages cannot solve');
 const items=[
  ['1','Everyone responds differently','The same meal produces very different glucose responses across individuals. Population-level guidelines are therefore sub-optimal for almost everyone.',BLUE],
  ['2','Everything is coupled in time','Glucose depends on carbohydrates, insulin, activity, stress, sleep and hormones — all interacting. It is hard to predict beyond a few tens of minutes.',ORANGE],
 ];
 items.forEach((it,i)=>{
   const y=1.95+i*1.85;
   card(s,0.55,y,7.6,1.6);
   circleNum(s,0.9,y+0.36,it[0],it[3]);
   s.addText(it[1],{x:1.55,y:y+0.22,w:6.4,h:0.36,fontSize:17,bold:true,color:INK,fontFace:F,margin:0});
   s.addText(it[2],{x:1.55,y:y+0.62,w:6.4,h:0.86,fontSize:12.5,color:GREY,fontFace:F,lineSpacing:17,margin:0});
 });
 card(s,8.5,1.95,4.25,3.5,INK);
 s.addText('537M',{x:8.7,y:2.35,w:3.85,h:0.95,fontSize:52,bold:true,color:LIGHT,fontFace:FH,align:'center',margin:0});
 s.addText('adults living with diabetes\nworldwide',{x:8.7,y:3.3,w:3.85,h:0.7,fontSize:13,color:'AFC3D4',fontFace:F,align:'center',lineSpacing:18,margin:0});
 s.addText('Type 2 accounts for over 90 % of cases\nand is largely driven by lifestyle',
   {x:8.7,y:4.15,w:3.85,h:0.8,fontSize:12,color:ORANGE,fontFace:F,align:'center',italic:true,lineSpacing:17,margin:0});
 foot(s,'Hakim DJOMO',2);
 s.addNotes("HAKIM — 1 min 15\n\nLe diabete touche plus de 500 millions d'adultes, et le type 2 represente plus de 90 % des cas.\n\nDeux difficultes rendent la prise en charge standardisee inefficace.\n\nPremierement, la variabilite entre individus : a repas identique, la reponse glycemique change enormement d'une personne a l'autre. Une recommandation moyenne n'est optimale pour presque personne.\n\nDeuxiemement, la dynamique temporelle : la glycemie depend de facteurs couples — glucides, insuline, activite, stress, sommeil, hormones. C'est un systeme difficile a anticiper.\n\nD'ou l'idee du jumeau numerique.");
}

/* ============ 3. LE JUMEAU + LE MANQUE ============ */
{const s=S(); light(s);
 title(s,'Digital twins: promise, and a gap','A dynamic virtual replica of the patient, continuously updated with real data');
 card(s,0.55,1.9,5.6,2.15);
 s.addText('The promise',{x:0.85,y:2.08,w:5,h:0.34,fontSize:16,bold:true,color:BLUE,fontFace:F,margin:0});
 s.addText([
  {text:'HbA1c reductions of 1.8 to 2.9 points',options:{bullet:true,breakLine:true}},
  {text:'Type 2 remission rates of 60 to 76 %',options:{bullet:true,breakLine:true}},
  {text:'Medication reduced in ~74 % of patients',options:{bullet:true}},
 ],{x:0.9,y:2.5,w:5.1,h:1.4,fontSize:12.5,color:INK,fontFace:F,paraSpaceAfter:6,margin:0});

 card(s,6.4,1.9,6.35,2.15,'FDF0EA');
 s.addText('The gap we found',{x:6.7,y:2.08,w:5.8,h:0.34,fontSize:16,bold:true,color:ORANGE,fontFace:F,margin:0});
 s.addText('Four requirements matter — accuracy, interpretability, fairness, validability. Reviewing the literature, we found work on each one separately, but no diabetes twin that addresses all four together.',
  {x:6.7,y:2.5,w:5.8,h:1.4,fontSize:12.5,color:INK,fontFace:F,lineSpacing:17,margin:0});

 const cols=['Accuracy','Interpretability','Fairness','Validability'];
 const rows=[['Transformer + LSTM (2025)',3,0,0,1],['Twin Health RCT (2022-24)',3,0,0,2],
             ['SHAP glucose studies (2025)',3,2,0,0],['Adversarial debiasing (2026)',2,0,2,1],
             ['VVUQ frameworks (2025)',0,1,0,3]];
 s.addText('No published work covers all four columns',{x:0.55,y:4.25,w:6,h:0.3,fontSize:13,bold:true,color:INK,fontFace:F,margin:0});
 const x0=0.55, y0=4.65, cw=[3.5,1.5,2.1,1.4,1.6];
 cols.forEach((c,j)=>{
   const xx=x0+cw.slice(0,j+1).reduce((a,b)=>a+b,0);
   s.addText(c,{x:xx-cw[j+1]+cw[j+1],y:y0,w:cw[j+1],h:0.3,fontSize:10.5,bold:true,color:GREY,fontFace:F,align:'center',margin:0});
 });
 rows.forEach((r,i)=>{
   const yy=y0+0.36+i*0.36;
   s.addText(r[0],{x:x0,y:yy,w:cw[0],h:0.32,fontSize:11,color:INK,fontFace:F,margin:0});
   for(let j=1;j<=4;j++){
     const xx=x0+cw.slice(0,j).reduce((a,b)=>a+b,0);
     const v=r[j], col= v===3?TEAL : v===2?BLUE : v===1?'C6D2DC' : 'EDF1F5';
     s.addShape(p.ShapeType.roundRect,{x:xx+cw[j]/2-0.42,y:yy+0.06,w:0.84,h:0.2,rectRadius:0.05,fill:{color:col}});
   }
 });
 [['strong',TEAL],['partial',BLUE],['weak / absent','EDF1F5']].forEach((L,k)=>{
   const lx=8.15+k*1.6;
   s.addShape(p.ShapeType.roundRect,{x:lx,y:4.29,w:0.4,h:0.18,rectRadius:0.04,fill:{color:L[1]},line:{color:LINE,width:0.5}});
   s.addText(L[0],{x:lx+0.48,y:4.22,w:1.15,h:0.3,fontSize:9.5,color:GREY,fontFace:F,valign:'middle',margin:0});
 });
 foot(s,'Jean Direl NZE',3);
 s.addNotes("JEAN DIREL — 1 min 45\n\nLe jumeau numerique est une replique virtuelle du patient, mise a jour en continu par ses donnees reelles.\n\nLes resultats publies sont spectaculaires : des baisses d'HbA1c de 1,8 a 2,9 points, des taux de remission du diabete de type 2 entre 60 et 76 %.\n\nMais en faisant notre revue de litterature, nous avons constate quelque chose. Quatre exigences comptent pour qu'un jumeau soit utilisable : la precision, l'interpretabilite, l'equite entre patients, et la validabilite.\n\nCe tableau resume ce que nous avons trouve. Chaque travail excelle sur une colonne ou deux. AUCUN ne couvre les quatre. C'est le manque que nous avons voulu adresser.");
}

/* ============ 4. LA THESE ============ */
{const s=S(); dark(s);
 s.addShape(p.ShapeType.ellipse,{x:-2.6,y:5.9,w:5,h:5,fill:{color:DEEP}});
 s.addText('Our thesis',{x:0.8,y:0.85,w:11.7,h:0.5,fontSize:16,bold:true,color:ORANGE,fontFace:F,charSpacing:2,margin:0});
 s.addText('At 30 minutes, glucose forecasting is a solved — and saturated — problem.',
  {x:0.8,y:1.5,w:11.7,h:0.95,fontSize:31,bold:true,color:LIGHT,fontFace:FH,lineSpacing:38,margin:0});
 s.addText('On real CGMacros data, a trained model scores 13.11 mg/dL. "Glucose will not move" scores 13.39.',
  {x:0.8,y:2.65,w:11.7,h:0.5,fontSize:15,color:'AFC3D4',fontFace:F,margin:0});

 const q=[['13.11','trained model'],['13.39','persistence baseline']];
 q.forEach((c,i)=>{
   const x=0.8+i*3.3;
   s.addShape(p.ShapeType.roundRect,{x,y:3.35,w:3.0,h:1.35,rectRadius:0.09,fill:{color:DEEP}});
   s.addText(c[0],{x,y:3.5,w:3.0,h:0.65,fontSize:34,bold:true,color:i?ORANGE:LIGHT,fontFace:FH,align:'center',margin:0});
   s.addText(c[1],{x,y:4.15,w:3.0,h:0.35,fontSize:11.5,color:'AFC3D4',fontFace:F,align:'center',margin:0});
 });
 s.addText('So the useful question is not "which model has the lowest error", but:',
  {x:0.8,y:5.05,w:11.7,h:0.4,fontSize:14,color:'AFC3D4',fontFace:F,italic:true,margin:0});
 s.addText('Where does forecasting actually have clinical value —\nand do we know when to trust it?',
  {x:0.8,y:5.5,w:11.7,h:0.9,fontSize:22,bold:true,color:ORANGE,fontFace:FH,lineSpacing:30,margin:0});
 s.addNotes("REGIS — 50 s\n\nVoici notre these, et elle est un peu provocatrice.\n\nA 30 minutes, la prevision glycemique est un probleme sature. Sur les vraies donnees de CGMacros, un modele entraine obtient 13,11 mg/dL d'erreur. Et la methode la plus bete du monde — dire que la glycemie ne bougera pas — obtient 13,39.\n\nAutrement dit : quasiment ex aequo. Des dizaines de publications optimisent un probleme deja resolu.\n\nLa question utile n'est donc pas 'quel modele a la plus petite erreur', mais : OU la prevision a-t-elle une valeur clinique reelle, et SAIT-ON quand lui faire confiance ?\n\nTout notre travail decoule de cette phrase.");
}

/* ============ 5. ARCHITECTURE ============ */
{const s=S(); light(s);
 title(s,'Our answer: an interpretable bottleneck','Instead of a black box, we force the model through physiologically meaningful concepts');
 const L=[
  ['0','Schedule','meals, activity,\nsleep, context','not learned',GREY],
  ['1','Metabolic state','14 readable concepts\nfrom physiology','not learned',TEAL],
  ['2','Glucose forecast','30 to 120 min,\nwith uncertainty','learned',BLUE],
  ['3','Risk states','probabilities and\ntraceable causes','calibrated',ORANGE],
 ];
 L.forEach((l,i)=>{
   const x=0.55+i*3.14;
   card(s,x,1.95,2.85,2.5);
   circleNum(s,x+0.28,2.2,l[0],l[4]);
   s.addText(l[1],{x:x+0.28,y:2.78,w:2.3,h:0.32,fontSize:15.5,bold:true,color:INK,fontFace:F,margin:0});
   s.addText(l[2],{x:x+0.28,y:3.14,w:2.35,h:0.75,fontSize:11.5,color:GREY,fontFace:F,lineSpacing:16,margin:0});
   s.addShape(p.ShapeType.roundRect,{x:x+0.28,y:3.95,w:1.45,h:0.28,rectRadius:0.07,fill:{color:l[3]==='learned'?BLUE:'EDF1F5'}});
   s.addText(l[3],{x:x+0.28,y:3.95,w:1.45,h:0.28,fontSize:9.5,bold:true,color:l[3]==='learned'?LIGHT:GREY,fontFace:F,align:'center',valign:'middle',margin:0});
   if(i<3) s.addText('→',{x:x+2.88,y:2.95,w:0.3,h:0.4,fontSize:19,color:'C6D2DC',fontFace:F,align:'center',margin:0});
 });
 card(s,0.55,4.75,12.2,1.5,'F0F7F3');
 s.addText('Why this matters',{x:0.9,y:4.92,w:4,h:0.3,fontSize:14,bold:true,color:TEAL,fontFace:F,margin:0});
 s.addText([
   {text:'Explainable by construction — ',options:{bold:true}},
   {text:'not "feature 7 weighed 0.3", but "your 45-min session burned ~38 g of carbohydrate".   '},
   {text:'Correctable — ',options:{bold:true}},
   {text:'a clinician can fix a concept and the forecast updates.   '},
   {text:'Traceable — ',options:{bold:true}},
   {text:'every recommendation points to the mechanism that triggered it.'},
 ],{x:0.9,y:5.26,w:11.5,h:0.85,fontSize:12.5,color:INK,fontFace:F,lineSpacing:18,margin:0});
 foot(s,'Xavier ONDO',5);
 s.addNotes("XAVIER — 1 min 50\n\nNotre reponse tient dans cette architecture en quatre couches.\n\nLa plupart des jumeaux vont directement des donnees a la glycemie, avec une boite noire au milieu. Nous, nous forcons le passage par un etat metabolique lisible.\n\nCouche 0 : l'emploi du temps — ce que la personne fait vraiment.\nCouche 1 : l'etat metabolique. QUATORZE concepts physiologiques. Et point crucial : cette couche N'EST PAS APPRISE. Ce sont des equations publiees — les METs du Compendium, les equations de Frayn de 1983, la cinetique d'absorption, le rythme circadien.\nCouche 2 : la prevision, elle, est apprise.\nCouche 3 : la traduction en etats de risque.\n\nCette idee porte un nom en machine learning : les Concept Bottleneck Models. Nous ne l'avons pas trouvee appliquee a la glycemie.\n\nTrois avantages concrets. C'est explicable par construction. C'est corrigeable — un clinicien peut rectifier un concept. Et c'est tracable — chaque conseil pointe son mecanisme.\n\nPassons a la demonstration.");
}

/* ============ 6. DEMO ============ */
{const s=S(); dark(s);
 s.addShape(p.ShapeType.ellipse,{x:10.8,y:-1.2,w:5.2,h:5.2,fill:{color:DEEP}});
 s.addText('LIVE DEMO',{x:0.8,y:1.55,w:9,h:0.45,fontSize:15,bold:true,color:ORANGE,fontFace:F,charSpacing:3,margin:0});
 s.addText('GlucoTwin',{x:0.8,y:2.05,w:9,h:0.95,fontSize:46,bold:true,color:LIGHT,fontFace:FH,margin:0});
 const steps=[
  'Edit the day — meals, activities from a 78-item catalogue',
  'Hover the curve — the metabolic concepts update live',
  'Compare interventions — six alternative days, ranked',
 ];
 steps.forEach((t,i)=>{
   const y=3.25+i*0.72;
   s.addShape(p.ShapeType.ellipse,{x:0.85,y:y+0.03,w:0.34,h:0.34,fill:{color:ORANGE}});
   s.addText(String(i+1),{x:0.85,y:y+0.03,w:0.34,h:0.34,fontSize:13,bold:true,color:LIGHT,align:'center',valign:'middle',fontFace:F,margin:0});
   s.addText(t,{x:1.35,y:y,w:9,h:0.4,fontSize:15,color:LIGHT,fontFace:F,valign:'middle',margin:0});
 });
 s.addText('Single self-contained HTML file — no install, no server, works offline',
  {x:0.8,y:5.7,w:9.6,h:0.35,fontSize:12,color:GREY,fontFace:F,italic:true,margin:0});
 s.addNotes("XAVIER (demo au clavier) — 3 min\n\nDEROULE — repeter au moins deux fois avant le jour J.\n\n1. Poser l'architecture : montrer le bandeau des 4 couches en haut de l'app. 'On retrouve exactement les couches de la slide precedente.'\n\n2. Montrer le probleme : pic a 248 mg/dL vers 22h. Lire l'explication en bas : le modele dit POURQUOI, pas seulement COMBIEN.\n\n3. Survoler la courbe vers 22h : les concepts se mettent a jour en direct. 'A cet instant le corps absorbe encore tant de glucides, et la sensibilite a l'insuline est tombee a 0,83.'\n\n4. LE MOMENT FORT — le comparateur d'interventions. Le jumeau simule six journees alternatives completes et les classe. Reduire les glucides : -46 mg/dL. Passer en index glycemique bas : -43. Avancer le repas de 3 h : seulement -4.\n   Insister : c'est un RESULTAT MESURE, pas une intuition. Et il contredit l'idee recue selon laquelle l'heure du repas pese autant que sa composition.\n\n5. Monter le phenomene de l'aube a 1,6 : la glycemie remonte avant le reveil, sans aucun repas. Un mecanisme que le patient ne peut pas deviner seul.\n\nPLAN B si la demo plante : captures d'ecran dans le dossier docs/figures. Ne jamais debugger devant le jury.");
}

/* ============ 7. PROTOCOLE ============ */
{const s=S(); light(s);
 title(s,'How we evaluate — three non-negotiable rules','Most of the credibility of this project sits in this slide');
 const R=[
  ['Leave-one-patient-out','Each patient is tested having never been seen in training. Neighbouring CGM samples from one person are highly correlated — a random split would be far too optimistic.',BLUE],
  ['Always against persistence','"Glucose will not move" is a brutal baseline at short horizons. A model that cannot beat it adds nothing, whatever its RMSE.',ORANGE],
  ['Always with uncertainty','Conformal prediction gives intervals with a coverage guarantee, without assuming anything about the error distribution.',TEAL],
 ];
 R.forEach((r,i)=>{
   const y=1.95+i*1.42;
   card(s,0.55,y,8.0,1.25);
   s.addShape(p.ShapeType.ellipse,{x:0.85,y:y+0.42,w:0.4,h:0.4,fill:{color:r[2]}});
   s.addText(String(i+1),{x:0.85,y:y+0.42,w:0.4,h:0.4,fontSize:14,bold:true,color:LIGHT,align:'center',valign:'middle',fontFace:F,margin:0});
   s.addText(r[0],{x:1.45,y:y+0.16,w:6.9,h:0.32,fontSize:15.5,bold:true,color:INK,fontFace:F,margin:0});
   s.addText(r[1],{x:1.45,y:y+0.5,w:6.9,h:0.68,fontSize:11.5,color:GREY,fontFace:F,lineSpacing:16,margin:0});
 });
 card(s,8.85,1.95,3.9,4.26,INK);
 s.addText('Plus clinical metrics',{x:9.15,y:2.2,w:3.3,h:0.35,fontSize:14,bold:true,color:ORANGE,fontFace:F,margin:0});
 s.addText([
   {text:'Error by glycaemic zone',options:{bullet:true,breakLine:true}},
   {text:'Hypo / hyper event detection',options:{bullet:true,breakLine:true}},
   {text:'Paired Wilcoxon test',options:{bullet:true,breakLine:true}},
   {text:'95 % confidence intervals',options:{bullet:true}},
 ],{x:9.2,y:2.65,w:3.3,h:1.6,fontSize:12,color:LIGHT,fontFace:F,paraSpaceAfter:8,margin:0});
 s.addText('Because an excellent mean error can coexist with total blindness to hypoglycaemia.',
  {x:9.15,y:4.5,w:3.35,h:1.2,fontSize:12,color:'AFC3D4',fontFace:F,italic:true,lineSpacing:17,margin:0});
 foot(s,'Seth NDINGA',7);
 s.addNotes("SETH — 1 min 20\n\nCette slide est celle ou se joue la credibilite de tout le projet.\n\nTrois regles, tenues par construction dans notre code.\n\nUn : leave-one-patient-out. Chaque patient sert de test sans jamais avoir ete vu a l'entrainement. Les mesures CGM d'une meme personne sont tres correlees entre elles ; un decoupage aleatoire donnerait des resultats bien trop optimistes.\n\nDeux : toujours compare a la persistance. C'est une baseline redoutable a court horizon.\n\nTrois : toujours avec une incertitude, par prediction conforme — qui garantit la couverture annoncee sans hypothese sur la distribution des erreurs.\n\nEt nous ajoutons des metriques cliniques, parce qu'une erreur moyenne excellente peut coexister avec une incapacite totale a detecter une hypoglycemie.");
}

/* ============ 8. RESULTAT 1 ============ */
{const s=S(); light(s);
 title(s,'Result 1 — the advantage grows with the horizon','45 virtual patients, leave-one-patient-out, HistGradientBoosting');
 s.addImage({path:FIG+'02_horizons.png',x:0.55,y:1.85,w:12.2,h:3.49});
 const st=[['+2.06','30 min'],['+2.83','60 min'],['+4.19','90 min'],['+5.72','120 min']];
 st.forEach((c,i)=>{
   const x=0.55+i*3.14;
   card(s,x,5.5,2.85,0.95, i===3?'FDF0EA':WASH);
   s.addText(c[0],{x,y:5.6,w:2.85,h:0.48,fontSize:23,bold:true,color:i===3?ORANGE:INK,fontFace:FH,align:'center',margin:0});
   s.addText(c[1]+'  ·  mg/dL gained',{x,y:6.06,w:2.85,h:0.3,fontSize:10.5,color:GREY,fontFace:F,align:'center',margin:0});
 });
 s.addText('All p < 1e-7  ·  42 of 45 patients improved at 120 min  ·  synthetic cohort',
  {x:0.55,y:6.5,w:12.2,h:0.3,fontSize:11,color:GREY,fontFace:F,italic:true,margin:0});
 foot(s,'Seth NDINGA',8);
 s.addNotes("SETH — 1 min\n\nPremier resultat. L'avantage du modele sur la persistance TRIPLE entre 30 et 120 minutes : de 2 a presque 6 mg/dL.\n\nTous les tests sont hautement significatifs, et a 120 minutes le modele est meilleur pour 42 patients sur 45.\n\nLe troisieme panneau est important : un point par patient. La dispersion grandit avec l'horizon — nous ne cachons pas que certains patients restent mal predits.\n\nUne precision d'honnetete : notre cohorte est SYNTHETIQUE, et elle rend la tache plus facile qu'en realite. Ce qu'il faut retenir, ce n'est pas la valeur absolue a 30 minutes, c'est la PENTE. C'est elle qui se transferera aux vraies donnees.");
}

/* ============ 9. RESULTAT 2 — LA CONTRADICTION ============ */
{const s=S(); light(s);
 title(s,'Result 2 — the contradiction','The two metrics disagree, and the cause is measurable');
 s.addImage({path:FIG+'05_mae_vs_clinical.png',x:0.55,y:1.8,w:12.2,h:3.49});
 card(s,0.55,5.45,12.2,1.35,INK);
 s.addText('At 120 minutes the model gains 5.72 mg/dL on the baseline — and detects only 1.7 % of hyperglycaemic events.',
  {x:0.9,y:5.62,w:11.5,h:0.4,fontSize:15.5,bold:true,color:LIGHT,fontFace:F,margin:0});
 s.addText('The prediction spread collapses from 0.87 to 0.69 times the real spread: the model retreats to the mean. It stops daring to announce extremes — exactly the events that matter to a patient.',
  {x:0.9,y:6.02,w:11.5,h:0.62,fontSize:12,color:'AFC3D4',fontFace:F,lineSpacing:17,margin:0});
 foot(s,'Seth NDINGA',9);
 s.addNotes("SETH — 1 min 20\n\nVoici notre resultat le plus important, et c'est une contradiction.\n\nPanneau 1 : la MAE dit que ca s'ameliore avec l'horizon. Panneau 2 : la detection des hyperglycemies dit exactement l'inverse — elle s'effondre de 44 % a moins de 2 %.\n\nDeux metriques, sur le meme modele, verdicts opposes.\n\nPanneau 3 : la cause, mesuree. L'ecart-type des predictions tombe a 0,69 fois celui des vraies valeurs. Le modele se refugie dans la moyenne. Plus l'horizon s'allonge, moins il ose annoncer les valeurs extremes.\n\nEt les valeurs extremes, c'est precisement ce qui compte pour le patient.\n\nC'est la demonstration de notre titre : optimiser la precision moyenne ne rend pas un jumeau cliniquement utile. C'est pour ca que nous mesurons quatre choses, et pas une.");
}

/* ============ 10. RESULTAT 3 — ABLATION ============ */
{const s=S(); light(s);
 title(s,'Result 3 — do the metabolic concepts earn their place?','Removing them one group at a time is the experiment that justifies layer 1');
 s.addImage({path:FIG+'03_ablation.png',x:0.55,y:1.9,w:7.6,h:2.77});
 const rows=[['Glucose history only','19.00',GREY],['+ meals','13.81',BLUE],['+ activity','12.84',BLUE],['+ modulators','12.51',TEAL]];
 card(s,8.45,1.9,4.3,2.77);
 s.addText('Mean absolute error (mg/dL)',{x:8.75,y:2.05,w:3.7,h:0.3,fontSize:11,bold:true,color:GREY,fontFace:F,margin:0});
 rows.forEach((r,i)=>{
   const y=2.42+i*0.55;
   s.addText(r[0],{x:8.75,y,w:2.5,h:0.32,fontSize:12,color:INK,fontFace:F,valign:'middle',margin:0});
   s.addText(r[1],{x:11.25,y,w:1.2,h:0.32,fontSize:15,bold:true,color:r[2],fontFace:FH,align:'right',valign:'middle',margin:0});
 });
 card(s,0.55,4.85,12.2,1.35,'FDF0EA');
 s.addText('Concepts cut the error by 34 % — but on synthetic data this is partly circular.',
  {x:0.9,y:5.0,w:11.5,h:0.38,fontSize:15,bold:true,color:INK,fontFace:F,margin:0});
 s.addText('Our synthetic glucose is generated from the very concepts the model receives, so it was always going to help. This experiment proves the pipeline detects a signal when one exists. Whether the concepts genuinely help is the decisive experiment — and it needs real data.',
  {x:0.9,y:5.4,w:11.5,h:0.68,fontSize:12,color:GREY,fontFace:F,lineSpacing:16,margin:0});
 foot(s,'Jean Direl NZE',10);
 s.addNotes("JEAN DIREL — 50 s\n\nTroisieme resultat, et c'est celui qui justifie toute la couche 1.\n\nOn empile les groupes de concepts. Avec l'historique glycemique seul : 19 mg/dL d'erreur. En ajoutant les repas : 13,8. L'activite : 12,8. Les modulateurs : 12,5. Soit 34 % de mieux.\n\nMAIS — et c'est important de le dire nous-memes avant qu'on nous le demande — sur des donnees synthetiques ce resultat est partiellement circulaire. Notre glycemie simulee est engendree A PARTIR des concepts que le modele recoit. Qu'ils aident etait joue d'avance.\n\nCe que cette experience prouve, c'est que notre pipeline detecte un signal quand il y en a un. Savoir si les concepts aident VRAIMENT, c'est l'experience decisive, et elle demande des donnees reelles.");
}

/* ============ 11. LIMITES ============ */
{const s=S(); light(s);
 title(s,'What we cannot claim','Stating this ourselves is part of the method');
 const lim=[
  ['Synthetic data','No real patient was used. These results validate the software and the protocol, not physiology.',ORANGE],
  ['An estimation chain','VCO2 is never measured outside a lab, so substrate partitioning carries about 25 % uncertainty — which we display rather than hide.',ORANGE],
  ['No clinical validity','No dose, no treatment, no diagnosis. This is a teaching prototype.',ORANGE],
  ['Fairness untested','Our cohort contained no hypoglycaemic events, so the most clinically important detection could not be evaluated.',ORANGE],
 ];
 lim.forEach((l,i)=>{
   const x=0.55+(i%2)*6.35, y=1.95+Math.floor(i/2)*1.75;
   card(s,x,y,5.95,1.5);
   s.addShape(p.ShapeType.ellipse,{x:x+0.28,y:y+0.28,w:0.36,h:0.36,fill:{color:l[2]}});
   s.addText('!',{x:x+0.28,y:y+0.28,w:0.36,h:0.36,fontSize:15,bold:true,color:LIGHT,align:'center',valign:'middle',fontFace:F,margin:0});
   s.addText(l[0],{x:x+0.8,y:y+0.24,w:4.9,h:0.32,fontSize:15,bold:true,color:INK,fontFace:F,margin:0});
   s.addText(l[1],{x:x+0.8,y:y+0.6,w:4.9,h:0.78,fontSize:11.5,color:GREY,fontFace:F,lineSpacing:16,margin:0});
 });
 card(s,0.55,5.5,12.2,0.95,'F0F7F3');
 s.addText('The honest reporting of what does not work is what separates research from a sales pitch.',
  {x:0.9,y:5.68,w:11.5,h:0.6,fontSize:14,bold:true,color:TEAL,fontFace:F,italic:true,valign:'middle',margin:0});
 foot(s,'Jean Direl NZE',11);
 s.addNotes("JEAN DIREL — 50 s\n\nCe que nous ne pouvons PAS affirmer.\n\nPremier point, le plus important : aucune donnee reelle. Nos resultats valident le logiciel et le protocole, pas la physiologie.\n\nDeuxieme : notre couche 1 est une chaine d'ESTIMATION, pas de mesure. Le VCO2 n'est mesurable qu'en laboratoire, donc la partition glucides-lipides porte environ 25 % d'incertitude. Nous l'AFFICHONS plutot que de la masquer.\n\nTroisieme : aucune validite clinique. Aucune dose, aucun traitement.\n\nQuatrieme : notre cohorte ne contenait aucune hypoglycemie, donc la detection la plus importante cliniquement n'a pas pu etre evaluee.\n\nEnoncer soi-meme ses limites fait partie de la methode. C'est ce qui separe la recherche d'un argumentaire commercial.");
}

/* ============ 12. CONCLUSION ============ */
{const s=S(); dark(s);
 s.addShape(p.ShapeType.ellipse,{x:10.2,y:3.9,w:5.5,h:5.5,fill:{color:DEEP}});
 s.addText('What we contribute',{x:0.8,y:0.75,w:11.7,h:0.45,fontSize:15,bold:true,color:ORANGE,fontFace:F,charSpacing:2,margin:0});
 s.addText('Most digital twins predict a number.\nOurs explains a mechanism.',
  {x:0.8,y:1.3,w:11,h:1.1,fontSize:29,bold:true,color:LIGHT,fontFace:FH,lineSpacing:38,margin:0});
 s.addText('From what you do, to what your body consumes, to what your glucose becomes, to what you can change — every step readable and checkable.',
  {x:0.8,y:2.5,w:10.5,h:0.6,fontSize:14,color:'AFC3D4',fontFace:F,lineSpacing:20,margin:0});

 const C=[['Interpretable by design','a physiological bottleneck, not post-hoc explanations'],
          ['Honest evaluation','leave-one-patient-out, persistence baseline, guaranteed intervals'],
          ['A measured contradiction','better mean error, worse clinical detection']];
 C.forEach((c,i)=>{
   const y=3.35+i*0.83;
   s.addShape(p.ShapeType.ellipse,{x:0.85,y:y+0.06,w:0.3,h:0.3,fill:{color:ORANGE}});
   s.addText(c[0],{x:1.3,y:y,w:4.1,h:0.4,fontSize:14,bold:true,color:LIGHT,fontFace:F,valign:'middle',margin:0});
   s.addText(c[1],{x:5.5,y:y,w:5.6,h:0.4,fontSize:12,color:'AFC3D4',fontFace:F,valign:'middle',margin:0});
 });
 s.addText('Next: plug in real CGMacros data — 45 real participants. The protocol is frozen, which is what will make the answer credible.',
  {x:0.8,y:5.95,w:10.6,h:0.55,fontSize:12.5,color:ORANGE,fontFace:F,italic:true,lineSpacing:17,margin:0});
 s.addText('github.com/…/GlucoTwin',{x:0.8,y:6.6,w:6,h:0.3,fontSize:11,color:GREY,fontFace:F,margin:0});
 s.addNotes("REGIS — 50 s\n\nPour conclure.\n\nLa plupart des jumeaux numeriques predisent un chiffre. Le notre explique un mecanisme : de ce que vous faites, a ce que votre corps consomme, a ce que votre glycemie devient, jusqu'a ce que vous pouvez changer. Chaque etape lisible et verifiable.\n\nTrois contributions. Un jumeau interpretable PAR CONSTRUCTION, pas avec des explications rajoutees apres coup. Une evaluation honnete, avec leave-one-patient-out, baseline de persistance et intervalles garantis. Et un resultat mesure : la contradiction entre precision moyenne et utilite clinique.\n\nLa suite, c'est brancher les vraies donnees de CGMacros — 45 participants reels. Notre protocole est deja fige, et c'est precisement ce qui rendra la reponse credible : nous ne pourrons pas etre accuses de l'avoir ajuste apres coup.\n\nMerci, nous sommes prets pour vos questions.");
}

p.writeFile({fileName: __dirname + '/../docs/GlucoTwin_presentation.pptx'}).then(f=>console.log('ecrit :',f));
