# Open Questions for AI While Exploring Hummingbot

	• Map out the key components in the repo
	• Explain what the "connector" layer does and where it lives in the code
	• Show me how a strategy interacts with connectors
	• Where is the code that places market and limit orders?
	• How does it keep track of the orders?
	• What happens if the app crashes with outstanding orders?
	• After restart can it continue keeping track of the orders?
	• Same for positions, what happp[ens after stoppimng or crashing of the app
	• After restart can it find them and keep track?
	• How does a connector implement rate limits?
	• Which class handles order fill events?
	• Can I simulate this locally, or do I need a live connection to test?
