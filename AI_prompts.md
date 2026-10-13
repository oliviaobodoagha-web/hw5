# AI Prompts Log: Homework 5 (Campus Customs Multi-Agent Operations)

This file logs what I typed to my AI coding assistant, in my own words. There is one section per problem.

## Problem 1: Vibe coder prompts

**Prompt 1**

> Create an AI_prompts.md to begin this assignment and keep it updated as I/we work. This file is the log of I type as a vibe coder. I will dscribe each problem to you in my own words. Put one sections for each problem. Each section must include: the problem number and title; at least one prompt that I typed in my own words as much as possible; and a follow up prompt if needed (if we do add, include one sentence on what wat lacking after the first).

No follow-up prompt was needed for this problem.

## Problem 2: Study the Campus Customs database

**Prompt 1**

> Open data/campus_customs.db so that I can see it I want to look at the table and its field. After you make it appear. copy the original file to data/campus_customs_new.db

**Follow-up prompt**

The first prompt only displayed the tables. Nothing was written down that explains why each table matters to the agents.

> Still part of prompt 2, start an output/harness.md. For each table, list the fields and one short line on why that table matters for the agents. We will keep growing this harness file in later probems

## Problem 3: Build the MCP Server

**Prompt 1**

> Wrtie an MCP server in mcp_server/ using FastMCP. It will talk to data/campus_customers_new.db. You do not need to connect or run it in this this problem. Ever agent in this homework uses the tools in this MCP server. We will add more tools to it later; for now write three tools tht I knwo I will need for the tickets in the database. Keep the names clear. Never invent any data, only yse unformation in the database. In output/harness.md list each of these three MCP tools. For every tool include which table it reads, which ticket it help unlock (101, 102, 103) and one sentence on why the tool is the right one for the ticket. Vague lines like "reads inventory" will get me a low score- tie the tool to the ticket. Also add a short mcp_server/README.md file that explains what the MCP server is for which data file it uses and the three tools it has. Before you get to this, run the 3 tools we'd defintiely need by me

**Follow-up prompt 1**

The first plan listed the three tools, but it did not show that each tool was really necessary for the tickets.

> I like this, but double check would we DEFINTELY need these tools?

**Follow-up prompt 2**

The third tool (`get_lease_and_cash`) only worked for one lease. It did not generalize to how the shop pays any bill, so it was replaced with `get_bills_and_cash`.

> for the last tool, yes it unlocks, but is it generalizable to the way we'd do business?

## Problem 4: Add the MCP Server to the vibe coder and test each tool

**Prompt 1**

> In claude add the MCP server to this project so that the vibe coder can call the tools. Save the connection JSON text in .mco.json at the project room (however your vibe coder saves local MCP server lists with Claude connected teast each of these three MCP tools. Save the evidence in output/mcp_smoke.json For every tool include: the prompt I asked the vibe coder, the tools name, the tool output which must match values in data/campus_customs_new.db

## Problem 5: Build the agent team and grow the MCP tools

**Prompt 1**

> Build the agentic team for Campus CUstoms using Pydantic AI: CVOss, Inventory, Acounting, Facilities, and customer Service, Include prompts, models and agent loops so they can delegate work to each other with full conectivity. Put the agent prompts in backend/prompts/_one file per agent. Put the data types in backend/models.py, and the agent files under backend/ (you layout can vary as long as the fice roles are clear. Use the portkey_api_key and only gpt-6-lune (or the claude equivalent) for every agent. I will write each prompt in my own words with the shop rules that the agent needs. More detailed prompt that cover all the aspects of the agent work and scope will give me a higher score. This part of the prblem isn't done first lets build each agent one by one. with the enough detial to get my full grade

**Follow-up prompt 1**

The first pass built the team's shared code, but none of the agent prompts had been reviewed for enough detail.

> run each agent by me one by oe so that i know that each agent has the proper detail to get me that full credit

**Follow-up prompt 2**

The Boss prompt described the job but never said clearly what was in and out of Boss's scope.

> what's in the agents scope and what is not in the agents scope?

**Follow-up prompt 3**

The Boss prompt treated each ticket alone. It did not cover shared cash across tickets, what happens after a human approves or rejects, or when to escalate.

> is there any aspect of your job you think you are missing?

**Follow-up prompt 4**

The Boss prompt referred to work (checking pending approvals, recording decisions) that no MCP tool could do yet.

> what are the tools neededed to do Bosses job?

**Follow-up prompt 5**

The MCP server only had read-only tools, so the team could not queue payments, post drafts, update tickets, or pay after approval.

> yes add all six tools now

**Follow-up prompt 6**

The Inventory prompt was written from scratch and did not reuse what we learned while building Boss (no duplicate orders, what happens after approval, escalation).

> pull any learnings from making boss, to make inventory

**Follow-up prompt 7**

The team could see stock but could not take it off the shelf when an order was filled, so two tickets could promise the same units. A `reserve_stock` tool was added.

> what would reserve_stock tool do

**Follow-up prompt 8**

All five agents were built and approved one at a time, but they had not yet been run together on the real tickets.

> approved, run the full team

**Follow-up prompt 9**

The team worked, but the backend still read some shop facts straight from the database instead of through MCP. Nothing recorded each agent step for a later audit, and the harness and README did not list every tool with its tables or have a safety section.

> Add any tools the agents need to MCP server so they can work on the open tickets. Shop facts come from the MCP server over data/campus_customs_new.db Do no invent a seconf shop-tools layer that bypasses MCP Wire the agents so they append to output/audit)trail.json as they run: for each agent-loop step, record enoug to audit later. Append to this file do not wipe it each run. In output/harnes In output slash harness.md, list each agent and each MCP tool, including the ones you add in this problem. Along with which table the tool uses, also add a safety section. The guardrails are real business, what a want, when agents touch real customers and real money, plus limits, that keep token use in check. Update MCP underscore server slash readme dot md so that the tool list matches what you have now., along with which table the tool uses. Also add a safety section, the guardrails a real business would want when agents touch real customers and real money plus limits that keep token use in check. Update MCP underscore server slash readme.md so that the tool list matches what you have now. Send.

## Problem 6: Plan the three tickets

**Prompt 1**

> Okay, so the title for problem six is plan the three tickets. So um, before we actually wire the back end, we're going to first write down what we expect the team to do on each open ticket. So before we build, I want you to write down what you expect to happen for ticket 101, ticket 102, and ticket 103. And after that, we will, I will give you the next directions.

**Follow-up prompt 1**

The plan said what each agent would do, but it never spelled out Boss's own part: how it routes each ticket, what it checks, and how it decides.

> what would the boss do in each of these instanes?

**Follow-up prompt 2**

The plan existed only as a markdown file. There was no page with one tab per ticket where the expected plan and, later, the actual run could sit side by side.

> Okay, now that it's established what I would expect each agent and each member of the team to do for each specific open ticket, I want you to now build output slash desk underscore tickets dot html. It's a page where you can double click with one tab per ticket. So a tab for 101, a tab for 102, a tab for 103. Also, add empty cache and reflection tabs for later problems. Leave them blank or with a short coming later note for now. On each ticket tab, fill an expected section only. Leave room for an actual section you will fill after the agents are ran. And for each ticket's expected section, you should write in my own words, like I'm doing now, um, who the boss should call first and why, all the agent delegations you expect, Um, not the boss essentially calls everyone, and which MCP tools uh, is it, are expected to run to use. Uh, plans that send every specialist on every ticket will give me a low score, so compare this plan to what actually happens when the agents are resolving these three tickets. Show me your work.

**Follow-up prompt 3**

The expected sections were done, but the comparison with a real run lived only in chat. The Actual sections on the page were still empty.

> yes run it and fill in the actual sections

**Follow-up prompt 4**

The run showed three gaps against the plan. Accounting requested rent while working the tee ticket. Boss sent Accounting in parallel before Facilities had checked the rent notice. Boss marked ticket 103 "blocked" when it was waiting on the customer's choice.

> yes tighten those prompts

**Follow-up prompt 5**

The prompts had been tightened but not tested. A second run was needed to show whether the fixes worked, kept next to the first run rather than replacing it.

> keep the current run and add the after tightening comparison

**Follow-up prompt 6**

After tightening, ticket 101 overcorrected to "needs_info" because the customer draft asked a question, even though the ticket was really waiting on the human to approve invoice #501.

> yes fix that

**Follow-up prompt 7**

"Never price below cost" was only written in the prompts, so nothing in code stopped an agent from offering a hoodie below its $22 cost. A `quote_price` tool and a price check in `post_draft` were added.

> yes lock the price rule in code

**Follow-up prompt 8**

The status fix and the price lock had each been tested on one ticket alone. A full run of all three tickets was needed to confirm everything works together.

> yes run the final full run

**Follow-up prompt 9**

The final run's customer message called the hoodies "Classic Navy Hoodies" instead of the catalog name "Basic Hoodie Big Yale". The price lock checked dollar amounts but not product names.

> yes fix the product name in code

## Problem 7: Backend routes

**Prompt 1**

> Ok so now while waiting we are gon So we're going to work on prompt seven, uh, the React front end dashboard, which is prompt seven. Problem seven will be named backend routes. Um, so the React front end dashboard, which is the next problem, needs a backend it can call. In backend slash main.py, use fast API and add routes that do the following. First, it returns the three tickets and whether each is opened or resolved. Second, it takes a ticket ID and runs your agent team on that ticket. Third, it returns recent agent events, what each agent said and which tools they used so that the board can refresh. Fourth, it approves a payment or purchase after a human clicks approve. Agents only prepare the pay. This route is what actually changes cash. Next, it returns the current checking balance from cash underscore accounts. And finally, it resets the database to the original values when you want to try a refresh run.

**Follow-up prompt 1**

The routes were built, but the harness listed them in a table without saying how to start the server from the backend folder. Each route also needed to be a single line giving its URL and what it does.

> from the backend slash folder start the server with uvicorn main:app --reload --port 8000 this code and this returns sorry this turns on the backend at http://localhost:8000 So the front end dashboard can call these routes. In output slash harness.md, list each route in one line. (what URL and also what it does), start the server with this code. And this returns, sorry, this turns on the backend at So the front end dashboard can call these routes. In output/harness.md lists each route in one line. (what URL/what ir does).

## Problem 8: Agent Dashboard

**Prompt 1**

> So problem eight is titled Agent Dashboard. We will now build the front end dashboard in front end slash with React plus Vite plus TypeScript. The page should call the routes you built in problem seven. At minimum, the board should list all three tickets. Let me pick one ticket and start the agent team on it. Show each agent and what they're saying, doing while the ticket runs. Mark a ticket resolved when the run finishes. Show a short summary of each agent, what each agent did on that ticket. Let a human approve a pay or purchase when asked and show the checking balance. It should drop after an approved pay. Make the dashboard look good. Be creative with the layout and the feel. This is a real desk that people want to sit at, so put thought into how it works. So for creative, I'm thinking um, like really professional lawyer meets J. Crew, very posh. Um, I want to keep my sort of like red accents, fancy, um, move away from the typical AI print so that it looks like an original.

**Follow-up prompt 1**

The first build reached the backend through a Vite proxy and didn't open the browser by itself. There was also no written record of the design choices.

> So once you're finished with that, um, I need the front end to talk to the back end. At thishttp://localhost:8000 On the back end, allow the Vite page origin. usually http://localhost:5173/ So that the browser is allowed to call those routes. Start the board with this. npm run dev This opens the React desk in my browser so that we can pick tickets and watch agents. output/design.md uh, with what I chose for the dashboard. Look at the layout, how the agents read differently. How resolved tickets and cash show up, and why. And include the creative choices that make it feel special and something that humans actually enjoy using.

## Problem 9: Resolve the tickets

**Prompt 1**

> So before testing the agents on a full run over three tickets, reset the working database data/campus_customs_new.db again so that we can start clean. Note the starting checking balance and run all three tickets on the board, 101, 102, 103, until each ticket is resolved. Open output/desk_tickets.html from problem six, open each ticket tab, and fill the actual section from this run: which agents worked, what they delegated, and which tools they used. Keep your expected section so that you can compare the two. On the cash section of the same output/desk_tickets.html, itemize the money: starting checking balance after the reset; for each ticket, how cash was managed, when the ticket resolved and why, which pay/purchase, and the dollar amount; then the ending checking balance. It must match cash_accounts in the working database. Wrong cash math loses points even if the board shows every ticket resolved. Also save output/resolved_tickets.json (for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals) and output/resolved_board.html (a page you can double click with a screenshot of your React board for each resolved ticket, 101, 102, and 103). Append real runs to output/audit_trail.json. Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

**Follow-up prompt 1**

The runs finished, but the payments were still waiting for a human signature, so no cash had moved and the ending balance couldn't be checked yet.

> ok I signed them, go ahead

## Problem 10: Reflection

**Prompt 1**

> OPen output/desk_tickets.html and fill the Reflection tab. Answer in my vibe. Make it sound like me, not like AI slop. Be detailed and thorough. Answer the following: How would you evalutate the perfomance of the agents on each tickets and why? For each ticket, how did actual compare to the Expected plan I wrote earlier? Describe three new problems Campus Customes might face that this agent team could solve with the tools we've build. Desctibe 3 new priblems Campus Customers might face that this agent team could not solve with the tools that I built, and explain the tools and agents I would need to solve them. Tie every answer to this app and the three tickets I ran _ use the ticket tabs and Cas tab on the same page as my evidence. Do not make this generic because if its generic you're gonna get me a low score

**Follow-up prompt 1**

The reflection used numbers from my runs, but the evidence wasn't pointed out answer by answer, and one closing paragraph drifted toward generic.

> Tie every answer to this app and the three tickets I ran _ use the ticket tabs and Cash tab on the same page as your evidence. Generic AI essays without Campus custums deatil will score low. DO do that to me.
