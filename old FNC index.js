const path = require("path");
const xml = require('xml');
const express = require('express');
const favicon = require('serve-favicon');
const axios = require("axios");
const bodyParser = require('body-parser');
const morgan = require('morgan');
const { writeData, readDataAsObject } = require("./xml");
const { ordinal_suffix_of } = require("./util");
const app = express();
const apiURL = "https://BASHMIX:47L1NyKJB1c2C54VQR5izc0XBlJZzVQMZfRTNRlN@api.challonge.com/v1";
const apiSubDomain = "";//"?subdomain=fnc-jo"
let sceneName = "";

// functions
const getParticipants = (req, onReady, onError) => readDataAsObject("data.xml", (error, data) => {
	if (error) {
		return next(error);
	}
	const tId = req.params && req.params.tId ? req.params.tId : data.items.tournament_id;
	axios.get(`${apiURL}/tournaments/${tId}/matches.json`)
		.then(({ data }) => {
			const matches = data;
			const roundsResults = matches.reduce((a, b) => {
				const match = b.match;
				const { player1_id, player2_id, scores_csv } = match;
				const scores = scores_csv.split("-");
				a[player1_id] = a[player1_id] || {
					wins: 0,
					loss: 0
				};
				a[player2_id] = a[player2_id] || {
					wins: 0,
					loss: 0
				};
				a[player1_id].wins = a[player1_id].wins + parseInt(scores[0] || 0);
				a[player1_id].loss = a[player1_id].loss + parseInt(scores[1] || 0);
				a[player2_id].wins = a[player2_id].wins + parseInt(scores[1] || 0);
				a[player2_id].loss = a[player2_id].loss + parseInt(scores[0] || 0);
				return a;
			}, {});
			const matchWins = matches.reduce((a, b) => {
				const match = b.match;
				const { player1_id, player2_id, winner_id } = match;
				if (winner_id) {
					if (player1_id === winner_id) {
						a[player1_id] = a[player1_id] ? a[player1_id] + 1 : 1;
					} else if (player2_id === winner_id) {
						a[player2_id] = a[player2_id] ? a[player2_id] + 1 : 1;
					}
				}
				return a;
			}, {});
			const matchLoses = matches.reduce((a, b) => {
				const match = b.match;
				const { player1_id, player2_id, winner_id } = match;
				if (winner_id) {
					if (player1_id !== winner_id) {
						a[player1_id] = a[player1_id] ? a[player1_id] + 1 : 1;
					} else if (player2_id !== winner_id) {
						a[player2_id] = a[player2_id] ? a[player2_id] + 1 : 1;
					}
				}
				return a;
			}, {});
			//const maxRate = Math.max(...Object.keys(rating).map(id => rating[id]));
			axios.get(`${apiURL}/tournaments/${tId}/participants.json`)
				.then(({ data }) => {
					const all = data.map(item => {
						const { participant } = item;
						participant.roundWins = roundsResults[participant.id] ? roundsResults[participant.id].wins : 0;
						participant.roundLoss = roundsResults[participant.id] ? roundsResults[participant.id].loss : 0;
						participant.matchWins = matchWins[participant.id] || 0;
						participant.matchLoses = matchLoses[participant.id] || 0;
						participant.score = participant.roundWins + ((participant.matchWins * 5) / (participant.matchLoses || 1))
						return participant;
					});
					const allSorted = all.sort((a, b) => {
						if (a.final_rank > b.final_rank) {
							return -1;
						} else if (b.final_rank > a.final_rank) {
							return 1;
						} else if (a.score > b.score) {
							return 1;
						} else if (b.score > a.score) {
							return -1;
						}
						return 0;
					});
					const maxScore = allSorted[allSorted.length - 1].score;
					const allRated = allSorted.map((a, index) => {
						a.rate = Math.round((a.score / maxScore) * 100) + "%";
						a.orderinal = ordinal_suffix_of(allSorted.length - index);
						return a;
					});
					onReady(allRated);
				})
				.catch(onError);
		})
		.catch(onError);
});

// view engine setup
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'ejs');

//logging
app.use(morgan('combined', {
	skip: function (req, res) { return (req.url.startsWith("/scene") || req.url.startsWith("/read")) && req.method === "GET" }
}))

// fav icon
app.use(favicon(path.join(__dirname, 'images', 'favicon.ico')));
app.use("/public", express.static(path.join(__dirname, 'public')));
app.use("/public\flags", express.static(path.join(__dirname, 'public\flags')));
app.use("/Build", express.static(path.join(__dirname, 'Build')));


// parse application/x-www-form-urlencoded
app.use(bodyParser.urlencoded({ extended: false }));

app.get('/tournaments', (req, res, next) => {
	axios.get(`${apiURL}/tournaments.json${apiSubDomain}`)
		.then(({ data }) => res.json(
			data.filter(({ tournament: { private } }) => !private))
		)
		.catch(next);
});

app.get('/matches/:tId?', (req, res, next) => {
	readDataAsObject("data.xml", (error, data) => {
		if (error) {
			return next(error);
		}
		const tId = req.params.tId || data.items.tournament_id;
		axios.get(`${apiURL}/tournaments/${tId}/matches.json`)
			.then(({ data }) => {
				const matches = data;
				axios.get(`${apiURL}/tournaments/${tId}/participants.json`)
					//	axios.get(`http://localhost:3000/participants`)
					.then(({ data }) => {
						const all = matches.map(item => {
							const match = item.match;
							item.player1 = data.find(({ participant: { id } }) => id === match.player1_id);
							item.player2 = data.find(({ participant: { id } }) => id === match.player2_id);
							return item;
						});
						res.json(all);
					})
					.catch(next);
			})
			.catch(next);
	});
});

app.get('/participants/:tId?', (req, res, next) => getParticipants(req, all => res.json(all), next));

app.post('/start', (req, res, next) => {
	const { data } = req.body;
	writeData("data.xml", JSON.parse(data || "{}"));
	res.send("ok");
});

app.get('/read', (req, res, next) => {
	readDataAsObject("data.xml", (error, data) => {
		if (error) {
			return next(error);
		}
		getParticipants(req, all => {
			const player1 = all.find(({ id }) => id + "" === data.items.player1_id[0]);
			const player2 = all.find(({ id }) => id + "" === data.items.player2_id[0]);
			data.items = Object.keys(data.items).reduce((a, b) => {
				a.push({ [b]: data.items[b] });
				return a;
			}, []);
			data.items = Object.keys(player1).reduce((a, b) => {
				a.push({ ["player1_" + b]: player1[b] });
				return a;
			}, data.items);
			data.items = Object.keys(player2).reduce((a, b) => {
				a.push({ ["player2_" + b]: player2[b] });
				return a;
			}, data.items);
			const xmlData = xml(data, { indent: "\t", declaration: true });
			return res.send(xmlData);
		}, next);
	});
});

// save scene
app.post('/scene', (req, res, next) => {
	const { scene } = req.body;
	sceneName = scene;
	res.send(sceneName + "");
});

// get scene
app.get('/scene', (req, res, next) => {
	res.send(sceneName + "");
});

app.get('/', (req, res) => {
	readDataAsObject("data.xml", (error, data) => {
		if (error) {
			return next(error);
		}
		res.render('index', { data });
	});
});

app.get('/chart', (req, res) => res.render('chart'));

app.get('/unity', (req, res) => res.render('unity'));

app.get('/brackets', (req, res, next) => {
	readDataAsObject("data.xml", (error, data) => {
		if (error) {
			return next(error);
		}
		axios
			.get(data.items.brackets[0])
			.then(({ data }) => res.send(data))
			.catch(next);
	});
});

// update scores to api
app.post('/send-scores/:tId/:mId', (req, res, next) => {
	const { tId, mId } = req.params;
	const { player1_id, player2_id, player1_score, player2_score, isSwitched } = req.body;
	const winner_id = parseInt(player1_score) > parseInt(player2_score) ? player1_id : player2_id;
	const scores_csv = parseInt(isSwitched) ? `${player2_score}-${player1_score}` : `${player1_score}-${player2_score}`;
	console.log(isSwitched, player1_score, player2_score, scores_csv);
	axios
		.put(`${apiURL}/tournaments/${tId}/matches/${mId}.json`, {
			match: {
				scores_csv,
				winner_id
			}
		})
		.then(() => res.send("ok"))
		.catch(next);
});

app.use((error, req, res, next) => {
	console.log(error);
	res.status(500).send(error.message);
});

app.listen(3000, () => console.log('Example app listening on port 3000!'));