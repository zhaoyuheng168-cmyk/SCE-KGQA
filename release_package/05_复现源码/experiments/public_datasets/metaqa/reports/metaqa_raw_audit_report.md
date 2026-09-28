# MetaQA Raw Data Audit Report

- Raw directory: `/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215/experiments/public_datasets/metaqa/raw/dataset/MetaQA_clean`
- Required files present: **19/19**
- Audit conclusion: **PASS**

## File Existence

| File | Exists | Lines |
|---|---:|---:|
| `kb.txt` | yes | 134741 |
| `1-hop/qa_train_qtype.txt` | yes | 96106 |
| `1-hop/vanilla/qa_train.txt` | yes | 96106 |
| `1-hop/qa_dev_qtype.txt` | yes | 9992 |
| `1-hop/vanilla/qa_dev.txt` | yes | 9992 |
| `1-hop/qa_test_qtype.txt` | yes | 9947 |
| `1-hop/vanilla/qa_test.txt` | yes | 9947 |
| `2-hop/qa_train_qtype.txt` | yes | 118980 |
| `2-hop/vanilla/qa_train.txt` | yes | 118980 |
| `2-hop/qa_dev_qtype.txt` | yes | 14872 |
| `2-hop/vanilla/qa_dev.txt` | yes | 14872 |
| `2-hop/qa_test_qtype.txt` | yes | 14872 |
| `2-hop/vanilla/qa_test.txt` | yes | 14872 |
| `3-hop/qa_train_qtype.txt` | yes | 114196 |
| `3-hop/vanilla/qa_train.txt` | yes | 114196 |
| `3-hop/qa_dev_qtype.txt` | yes | 14274 |
| `3-hop/vanilla/qa_dev.txt` | yes | 14274 |
| `3-hop/qa_test_qtype.txt` | yes | 14274 |
| `3-hop/vanilla/qa_test.txt` | yes | 14274 |

## Qtype / QA Alignment

| Hop | Split | Qtype lines | QA lines | Match |
|---:|---|---:|---:|---:|
| 1 | train | 96106 | 96106 | yes |
| 1 | dev | 9992 | 9992 | yes |
| 1 | test | 9947 | 9947 | yes |
| 2 | train | 118980 | 118980 | yes |
| 2 | dev | 14872 | 14872 | yes |
| 2 | test | 14872 | 14872 | yes |
| 3 | train | 114196 | 114196 | yes |
| 3 | dev | 14274 | 14274 | yes |
| 3 | test | 14274 | 14274 | yes |

## Knowledge Base Parse Check

- Total lines / triples: **134741**
- Expected total lines: **134741**
- Malformed lines: **0**
- Distinct subjects: **16427**
- Distinct objects: **26849**
- Distinct entities: **43234**
- Distinct relations: **9**

### Top 20 Relations

| Relation | Count |
|---|---:|
| `starred_actors` | 33735 |
| `has_tags` | 28944 |
| `written_by` | 19543 |
| `release_year` | 16726 |
| `directed_by` | 15966 |
| `has_genre` | 15895 |
| `in_language` | 3482 |
| `has_imdb_rating` | 328 |
| `has_imdb_votes` | 122 |

## QA Format Samples

### 1-hop / train

| Line | Qtype | Question | Answers | Warning |
|---:|---|---|---|---|
| 1 | tag_to_movie | what movies are about [ginger rogers] | Top Hat \|\| Kitty Foyle \|\| The Barkleys of Broadway |  |
| 2 | tag_to_movie | which movies can be described by [moore] | Fahrenheit 9/11 \|\| Far from Heaven |  |
| 3 | tag_to_movie | what films can be described by [occupation] | Red Dawn \|\| The Teahouse of the August Moon |  |
| 4 | tag_to_movie | which films are about [jacques tati] | Mon Oncle \|\| Playtime \|\| Trafic |  |
| 5 | tag_to_movie | what movies are about [donnie darko] | S. Darko |  |

### 1-hop / dev

| Line | Qtype | Question | Answers | Warning |
|---:|---|---|---|---|
| 1 | actor_to_movie | what movies did [Temuera Morrison] act in | Once Were Warriors \|\| Tracker \|\| River Queen |  |
| 2 | actor_to_movie | what movies did [Evelyn Venable] act in | Alice Adams \|\| Death Takes a Holiday \|\| The Little Colonel |  |
| 3 | actor_to_movie | what does [Tom Cullen] act in | Weekend |  |
| 4 | actor_to_movie | what movies was [Shareeka Epps] an actor in | Half Nelson |  |
| 5 | actor_to_movie | what does [Peter Franzén] appear in | Ambush \|\| Dog Nail Clipper \|\| On the Road to Emmaus |  |

### 1-hop / test

| Line | Qtype | Question | Answers | Warning |
|---:|---|---|---|---|
| 1 | actor_to_movie | what does [Grégoire Colin] appear in | Before the Rain |  |
| 2 | actor_to_movie | [Joe Thomas] appears in which movies | The Inbetweeners Movie \|\| The Inbetweeners 2 |  |
| 3 | actor_to_movie | what films did [Michelle Trachtenberg] star in | Inspector Gadget \|\| Black Christmas \|\| Ice Princess \|\| Harriet the Spy \|\| The Scribbler |  |
| 4 | actor_to_movie | what does [Helen Mack] star in | The Son of Kong \|\| Kiss and Make-Up \|\| Divorce |  |
| 5 | actor_to_movie | what films did [Shahid Kapoor] act in | Haider \|\| Jab We Met \|\| Chance Pe Dance |  |

### 2-hop / train

| Line | Qtype | Question | Answers | Warning |
|---:|---|---|---|---|
| 1 | director_to_movie_to_writer | which person wrote the films directed by [Yuriy Norshteyn] | Sergei Kozlov |  |
| 2 | movie_to_director_to_movie | which movies have the same director of [Just Cause] | The Mambo Kings |  |
| 3 | writer_to_movie_to_genre | what genres do the movies written by [Maureen Medved] fall under | Drama |  |
| 4 | actor_to_movie_to_year | what were the release years of the movies acted by [Todd Field] | 1998 \|\| 1993 |  |
| 5 | movie_to_writer_to_movie | what are the movies that have the same screenwriter of [Dodsworth] | Gone with the Wind \|\| Raffles \|\| Elmer Gantry \|\| Cass Timberlane \|\| Arrowsmith \|\| Mantrap |  |

### 2-hop / dev

| Line | Qtype | Question | Answers | Warning |
|---:|---|---|---|---|
| 1 | director_to_movie_to_language | what are the languages spoken in the films directed by [Joel Zwick] | Greek |  |
| 2 | actor_to_movie_to_year | the films acted by [Sharon Tate] were released in which years | 1967 \|\| 1968 |  |
| 3 | writer_to_movie_to_year | when did the films written by [Anthony Mann] release | 1949 \|\| 1947 |  |
| 4 | director_to_movie_to_genre | what genres do the movies directed by [Clark Gregg] fall under | Drama \|\| Comedy |  |
| 5 | writer_to_movie_to_year | when did the movies written by [Emir Kusturica] release | 1998 \|\| 1995 \|\| 2007 \|\| 1988 \|\| 1981 |  |

### 2-hop / test

| Line | Qtype | Question | Answers | Warning |
|---:|---|---|---|---|
| 1 | actor_to_movie_to_director | which person directed the movies starred by [John Krasinski] | Nancy Meyers \|\| Sam Mendes \|\| George Clooney \|\| Ken Kwapis \|\| Luke Greenfield |  |
| 2 | director_to_movie_to_director | who are movie co-directors of [Delbert Mann] | Franco Zeffirelli \|\| Cary Fukunaga \|\| Lewis Milestone \|\| Robert Stevenson |  |
| 3 | director_to_movie_to_language | what are the primary languages in the movies directed by [David Mandel] | German |  |
| 4 | writer_to_movie_to_writer | the screenwriter [Mimsy Farmer] co-wrote movies with who | Barbet Schroeder |  |
| 5 | actor_to_movie_to_genre | the films acted by [Shaun White] were in which genres | Sport \|\| Documentary |  |

### 3-hop / train

| Line | Qtype | Question | Answers | Warning |
|---:|---|---|---|---|
| 1 | movie_to_actor_to_movie_to_year | the films that share actors with the film [Dil Chahta Hai] were released in which years | 1997 \|\| 1998 \|\| 2003 \|\| 2001 \|\| 2006 \|\| 2004 \|\| 2005 \|\| 2014 \|\| 2008 \|\| 2009 \|\| 2010 \|\| 2012 |  |
| 2 | movie_to_writer_to_movie_to_director | who are the directors of the movies written by the writer of [The Green Mile] | Stephen King \|\| Frank Darabont \|\| Tobe Hooper \|\| Mick Garris \|\| Lawrence Kasdan \|\| Paul Michael Glaser \|\| John Carpenter \|\| Rob Reiner \|\| Mikael Håfström \|\| Brian De Palma \|\| Chuck Russell \|\| Donald P. Borchers \|\| George A. Romero \|\| Bryan Singer \|\| Tom Holland \|\| Fritz Kiersch \|\| Brett Leonard \|\| Stanley Kubrick \|\| Ralph S. Singleton \|\| Taylor Hackford \|\| Lewis Teague \|\| Mark L. Lester \|\| David Cronenberg \|\| Mark Pavia \|\| David Koepp \|\| Mary Lambert \|\| William Wyler \|\| Michael Gornick \|\| Scott Hicks |  |
| 3 | movie_to_actor_to_movie_to_director | which person directed the films acted by the actors in [Jawbreaker] | Chris D'Arienzo \|\| Jonathan Kesselman \|\| Joe Chappelle \|\| Robert Rodriguez \|\| Victor Salva \|\| Matthew Leutwyler \|\| Gregg Araki \|\| Mark Duplass \|\| Jared Drake |  |
| 4 | movie_to_actor_to_movie_to_director | who is listed as director of the movies starred by [December Boys] actors | Chris Columbus \|\| David Yates \|\| Alfonso Cuarón \|\| Mike Newell \|\| Alexandre Aja |  |
| 5 | movie_to_director_to_movie_to_genre | what types are the films directed by the director of [For Love or Money] | Action \|\| Comedy \|\| Western \|\| Thriller \|\| Crime |  |

### 3-hop / dev

| Line | Qtype | Question | Answers | Warning |
|---:|---|---|---|---|
| 1 | movie_to_director_to_movie_to_genre | the films that share directors with the film [Black Snake Moan] were in which genres | Drama \|\| Music |  |
| 2 | movie_to_director_to_movie_to_actor | who acted in the movies directed by the director of [Some Mother's Son] | Bill Paxton \|\| Don Cheadle \|\| Joaquin Phoenix |  |
| 3 | movie_to_director_to_movie_to_language | what are the languages spoken in the films whose directors also directed [Police] | French |  |
| 4 | movie_to_actor_to_movie_to_genre | the films that share actors with the film [The Harvey Girls] were in which genres | Mystery \|\| Family \|\| Horror \|\| Crime \|\| Drama \|\| Fantasy \|\| War \|\| Western \|\| Music \|\| Comedy \|\| Musical \|\| Thriller |  |
| 5 | movie_to_director_to_movie_to_writer | the films that share directors with the films [Following] are written by who | Christopher Priest \|\| Erik Skjoldbjærg \|\| Nikolaj Frobenius \|\| Jonathan Nolan \|\| Christopher Nolan \|\| David S. Goyer |  |

### 3-hop / test

| Line | Qtype | Question | Answers | Warning |
|---:|---|---|---|---|
| 1 | movie_to_director_to_movie_to_language | the films that share directors with the film [Catch Me If You Can] were in which languages | German \|\| Polish \|\| Mende \|\| Japanese |  |
| 2 | movie_to_director_to_movie_to_actor | who starred movies for the director of [Written on the Wind] | Sandra Dee \|\| Charles Coburn \|\| Cornel Wilde \|\| John Gavin \|\| Warren William \|\| Susan Kohner \|\| Joan Bennett \|\| Fred MacMurray \|\| Barbara Stanwyck \|\| Don Ameche \|\| Jane Wyman \|\| Rochelle Hudson \|\| Boris Karloff \|\| Patricia Knight \|\| Robert Cummings \|\| Rock Hudson \|\| Lucille Ball \|\| Claudette Colbert \|\| Lana Turner \|\| George Sanders |  |
| 3 | movie_to_actor_to_movie_to_language | the films that share actors with the film [Creepshow] were in which languages | Polish \|\| English |  |
| 4 | movie_to_writer_to_movie_to_year | what were the release years of the films that share writers with the film [Grown Ups 2] | 1995 \|\| 1996 \|\| 1999 \|\| 1998 \|\| 1989 \|\| 2002 \|\| 2000 \|\| 2008 \|\| 2011 \|\| 2010 |  |
| 5 | movie_to_actor_to_movie_to_director | who is listed as director of the films starred by [The Inner Circle] actors | John Landis \|\| Atom Egoyan \|\| Gary Trousdale \|\| Steven Spielberg \|\| Louis Leterrier \|\| Alan Alda \|\| Nora Ephron \|\| Wolfgang Petersen \|\| Allen Coulter \|\| Richard Benjamin \|\| Orson Welles \|\| Neil Jordan \|\| William Dieterle \|\| Stephen Frears \|\| Peter Yates \|\| Markus Schleinzer \|\| Wayne Wang \|\| Jean Delannoy \|\| Robert Zemeckis \|\| Guy Jenkin \|\| Christopher Hampton \|\| Jack Clayton \|\| Rocky Morton \|\| Annabel Jankel \|\| Mike Hodges \|\| Kirk Wise \|\| Ellen Perry \|\| John Byrum \|\| Abel Ferrara \|\| Robert M. Young |  |

## Anomalies (Maximum 20)

- None detected.

## Conclusion

Audit result: **PASS**.
All 19 files present: **yes**.
All qtype/QA line counts aligned: **yes**.
`kb.txt` malformed lines: **0**.
