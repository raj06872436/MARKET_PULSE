# User guide

MarketPulse shows what people are saying about the brands and products you follow: how much, how they feel, about which topics, and what's changing. Every number links back to the posts behind it, and days with no data are shown as "not collected", never as zero.

## Getting started

1. **Create an account.** Open the app and choose **Create account**. Passwords need at least 10 characters. The first account on a new installation is the admin, who can connect shared sources such as Bluesky.
2. **Make a watchlist.** On **Watchlists**, create a watchlist (for example "Budget phones") and add terms. Each term has a type (brand, product, competitor, hashtag or keyword) and optional variants: other spellings or hashtags that should count as the same thing, such as `#RedmiNote14`.
3. **Add data.** On **Sources**, upload a CSV of posts (see the [CSV format](csv-format.md); `data_samples/sample_mentions.csv` is a ready example) or, as admin, connect Bluesky after confirming you have checked its current terms. Each upload or sync is analysed straight away.
4. **Look at the dashboard.** The filter bar at the top of each page picks the watchlist, dates and sources. The filters are kept in the address, so a link you copy opens the same view for a colleague with access.

## Pages

**Overview.** Daily mentions for each term, with uncollected days shaded, then one card per term with its trend score (0 to 100, where 50 means no change), what's driving it, and example posts.

**Explore.** Every matched post, searchable and filterable by term, source, date, sentiment and topic. Use it to check what a number on another page is made of.

**Sentiment.** Positive, neutral and negative share over time; which topics (price, battery, camera, delivery, support and others) carry the most negative or positive posts; frequent phrases; and example posts for each side.

**Compare.** Your terms side by side: mentions, share of voice, net sentiment, negative share, engagement per post and how many days each was collected. A heat map shows each term's negative share per topic, and "Where terms differ" lists topics where one term stands out by 15 points or more. A post naming two terms counts for both.

**Forecasts.** Expected daily mentions for the next days with an 80% range. Each forecast shows how it did against simple baselines on past data. When the history is too short or too patchy, you see "Not enough reliable data" instead of a guess.

**Insights.** Short cards on what changed in the last 7 collected days against the 7 before: an observation, a possible explanation, a caveat and a next step. Open **Evidence** on any card to see every number it uses and the posts behind it. **Refresh** rewrites them from templates. If your administrator turned it on, **Write with Claude** lets Claude phrase them; each number Claude writes is checked against the data and cards that fail are dropped.

**Watchlists.** Add, rename, pause and remove terms. Each watchlist card also has **Alerts**.

**Sources.** Each source's health: last successful run, records fetched and matched, errors, and days not covered. Upload CSVs here and run syncs.

**Account.** Your email and role, sign out, and delete your account.

## Alerts

Open **Alerts** on a watchlist card to add one for a term. Choose a measure (daily mentions, weekly change in mentions, negative share or trend score), a threshold and a quiet period (6 hours, 1 day or 1 week). Alerts are checked after every upload or sync, on each term's latest collected day, and fire at most once per day. They show in the app on the watchlist card; nothing is emailed.

## Export

**Download daily totals (CSV)** on Explore and Compare downloads daily totals per term for the current filters: mentions, engagement, sentiment counts and shares, and whether each day was collected. It contains counts only, never post text.

## Reading the numbers

- **"Not collected"** means no source covered that day, so we don't know. It is different from a collected day with zero mentions.
- **Coverage** labels show how many days in the range were collected. Treat comparisons with low or uneven coverage carefully.
- **Engagement** (likes, comments and shares) is only counted where the source provides it. "Not given by source" means unknown, not zero.
- **Sentiment** comes from an automatic model and gets individual posts wrong, especially sarcasm and mixed opinions. Look at shares across many posts, and at the examples.
- **Trend score** and **insights** describe change in conversation volume and tone. They don't explain why something happened, and more mentions don't mean more sales.

## Privacy

Your watchlists, uploads, alerts and insights are visible only to your account. Deleting your account removes them along with everything you uploaded. Posts from shared sources (such as Bluesky) stay, since other accounts may track the same terms.
