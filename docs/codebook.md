# Annotation Manual for Political News Coverage

**Final version of the annotation protocol**

## 1. Purpose of this document

This manual defines the rules for annotating political articles from online
media in Bosnia and Herzegovina.

Each article is assessed along five dimensions:

1. dominant political actor;
2. tone toward the dominant political actor;
3. reporting frame (framing);
4. balance; and
5. political lean.

Every dimension is assessed from the content of the article itself and the
rules in this document.

## 2. Unit of analysis

One article constitutes one unit of analysis.

The annotation considers:

- the headline;
- the subheading or lead, if present;
- the main body text; and
- quotations and sources included in the article.

It does not consider:

- reader comments;
- related or recommended articles;
- advertisements;
- page-navigation elements; or
- information not contained in the article being analyzed.

The annotation is based on how the content is presented in the particular
article, not on the annotator's personal political views.

## 3. General annotation rules

Read the entire article before assigning labels.

Assess the dimensions in the following logical order:

1. identify the dominant political actor;
2. assess the tone toward that actor;
3. identify the dominant reporting frame;
4. assess balance; and
5. assess political lean.

Assess each dimension independently. In particular, do not conflate different
dimensions. For example:

- a negative tone toward a political actor does not automatically mean that
  the article supports the actor's opposition;
- a neutral tone does not automatically make an article balanced; and
- the presence of several sources does not automatically mean that different
  political perspectives are represented.

When assessing tone, first determine its direction—negative, neutral, or
positive—and then determine the intensity of the treatment. Do not choose a
less extreme value merely because it appears safer or because extreme values
are rarer. Base intensity on the strength of the editorial signals in the
article.

## 4. Dominant political actor

The dominant political actor is the person, political organization,
institution, or other political entity that is the article's main subject.

As a rule, select one dominant actor. If two or more actors genuinely receive
equal treatment as the article's main subject, they may be listed together.

The dominant actor is not automatically:

- the person who made a statement;
- the person quoted most often; or
- the politician mentioned first.

Determine whom or what the article is primarily about. Consider:

- the headline and lead;
- the amount of space devoted to the actor;
- the article's central topic; and
- the action or event around which the article is organized.

The permitted dominant-actor labels are defined in advance for the particular
article set. They include politicians, political parties, institutions, and
other political entities relevant to the corpus. Annotators must select the
dominant actor exclusively from this predefined label set.

Keep the label at the level on which the article is actually focused. If the
article is primarily about an institution, select the institution; if it is
primarily about a particular politician, select the politician; and if it is
primarily about a political party, select the party. A person making a
statement must not replace an institution or party as the dominant actor when
that person is not the article's real subject.

## 5. Tone

### 5.1. Definition

Tone describes how the dominant political actor is presented in the article.
Always assess tone in relation to the previously identified dominant actor.

Distinguish between:

- the article's tone toward the dominant actor; and
- the tone of statements that the dominant actor directs at other people.

For example, the fact that a politician sharply criticizes another politician
does not, by itself, mean that the article has a negative tone toward the
politician making the criticism.

### 5.2. Tone scale

- **-2 — Very negative:** markedly negative editorial treatment, forceful
  discrediting, or highly accusatory wording.
- **-1 — Negative:** clearly critical or unfavorable treatment of the actor,
  without strongly discrediting or propagandistic presentation.
- **0 — Neutral:** predominantly factual or procedural presentation without
  clearly positive or negative treatment.
- **+1 — Positive:** clearly favorable treatment of the actor, or uncritical
  space for the actor's position, without strongly promotional or celebratory
  treatment.
- **+2 — Very positive:** markedly laudatory, affirmative, idealizing, or
  strongly promotional treatment of the actor.

When distinguishing negative from very negative tone, or positive from very
positive tone, determine whether evaluative content comes only from a quoted
source or whether the outlet adopts, amplifies, or further shapes it. Harsh
criticism clearly attributed to a source does not, by itself, constitute very
negative tone. Similarly, merely relaying a favorable message without
criticism does not automatically constitute very positive tone.

The headline and lead carry substantial editorial weight. Extreme negative or
positive values are justified when there is an especially strong editorial
signal or several independent strong signals that consistently create such
treatment across the article. Repetition of the same claim in the headline,
lead, and body should not automatically be counted as several independent
signals.

Assess the entire article, paying particular attention to the headline, lead,
and wording used to describe the dominant actor.

## 6. Reporting frame (framing)

### 6.1. Definition

The reporting frame is the dominant way in which a political event is
presented and interpretively organized.

If several possible frames appear, select the one that has the dominant role
in presenting the event. Consider the whole article, especially the headline
and introduction.

### 6.2. Categories

The Bosnian tokens below are retained in the datasets and evaluator output:

- `konflikt` — **conflict:** emphasis on political conflict, disagreement,
  opposing sides, or competition.
- `odgovornost` — **responsibility:** emphasis on responsibility, blame,
  causes, or the consequences of someone's actions.
- `ekonomski` — **economic:** the event is presented primarily in terms of
  money, costs, economic benefit, or economic consequences.
- `moralni` — **moral:** the event is presented mainly through moral values,
  ethical condemnation, or questions of right and wrong.
- `proceduralni` — **procedural:** focus on institutions, laws, rules,
  decisions, votes, or other formal procedures.
- `nacionalni` — **national/ethnic:** emphasis on national or ethnic identity,
  relations, or collective interests. In the BiH context, *national* often
  refers to the constituent peoples and therefore carries an ethnic as well as
  a national meaning.
- `neutralan` — **neutral:** none of the interpretive frames above clearly
  dominates; the article is predominantly factual.

## 7. Balance

### 7.1. Definition

Balance indicates the extent to which an article presents different relevant
political perspectives on an event.

Do not assess only the number of people or sources quoted. Several sources
representing the same political position do not automatically amount to
several perspectives.

Background facts do not themselves constitute an additional political
perspective. A clearly quoted or paraphrased opposing political position
counts as a second perspective even when it is not a direct response to the
main statement. Merely mentioning another side without presenting its view or
argument does not constitute an additional perspective.

A factually or procedurally written article can be one-sided if it does not
contain several relevant political perspectives. Neutral tone must therefore
not be equated with balance.

### 7.2. Scale

- **0 — One-sided:** only one relevant political perspective is presented.
- **1 — Partly balanced:** an additional or opposing perspective is present,
  but receives substantially less space or is less fully developed.
- **2 — Balanced:** relevant different perspectives are presented with
  approximately equal weight.

## 8. Political lean

### 8.1. Definition

Political lean identifies the political option, or broader political-identity
option, favored by the article's manner of presentation.

Assess the presentation in the particular article, not the outlet's presumed
general political orientation.

Determine whether there is an editorial signal favoring a political option.
Such signals can include the construction of the headline; one-sided
amplification of a political or national/ethnic message; the selection of
quotations, space, and context; and evaluatively loaded language used by the
author.

One-sidedness alone is not sufficient to establish political lean. Likewise,
a positive or negative tone toward an individual actor does not automatically
give an article a corresponding political lean.

A plain account of a judicial, institutional, or procedural decision is
neutral if no additional editorial treatment favors a political option, even
when the outcome itself benefits or harms one side politically.

### 8.2. Categories

The original Bosnian tokens are retained in the data:

- `neutralan` — **neutral:** no clear signals favor a political option.
- `nejasno` — **unclear:** genuinely contradictory editorial signals prevent
  an unambiguous assessment of political lean.
- `pro_vlast` — **pro-government:** the presentation favors governing
  political structures at the relevant level of government.
- `pro_opozicija` — **pro-opposition:** the presentation favors opposition
  political structures.
- `pro_bosnjacka_opcija` — **pro-Bosniak option:** the presentation favors
  Bosniak political actors or interests.
- `pro_srpska_opcija` — **pro-Serb option:** the presentation favors Serb
  political actors or interests.
- `pro_hrvatska_opcija` — **pro-Croat option:** the presentation favors Croat
  political actors or interests.
- `pro_gradjanska_opcija` — **pro-civic option:** the presentation favors civic
  or multiethnic political options. Here, *civic* (`gradjanska`/`građanska`)
  denotes a non-ethnic or multiethnic political orientation in BiH discourse.

The identity-based categories describe the direction of an article's
editorial treatment; they do not label an outlet or an annotator's own views.

## 9. Final check before submitting an annotation

Before confirming the annotation, check:

1. Was the dominant actor selected from the predefined set of permitted
   labels?
2. Does the tone refer specifically to that actor?
3. Was one dominant reporting frame selected?
4. Does the balance rating reflect different perspectives, rather than merely
   the number of sources?
5. Was political lean determined from the particular article?
6. Were `neutralan` (neutral) and `nejasno` (unclear) distinguished correctly?
7. Is the assessment based on the article's content rather than personal
   political views?
