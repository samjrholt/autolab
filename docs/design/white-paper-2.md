# The Bottleneck in Materials Discovery Isn't the Model. It's the Lab.

Eras are defined by materials.

Bronze. Iron. Steel. Silicon. Every leap in human capability has been a materials breakthrough first. And right now, we need the next one badly: for energy production, quantum computing, medical devices, and geopolitical stability around critical minerals.

But materials discovery is slow. A new material can take 10–20 years from lab to production. AI is starting to change the prediction side of this, but there's a gap that nobody is closing fast enough.

## The prediction problem is evolving

In 2023, Google DeepMind's GNoME predicted 2.2 million new crystal structures. Microsoft's MatterGen can generate novel compositions on demand. ML interatomic potentials like MACE, NequIP, and CHGNet can estimate material properties at a fraction of the cost of traditional quantum mechanical calculations.

These are impressive results. But at the moment they mainly answer the question: *could this crystal structure exist stably?* That's useful. It's also not the only question that matters to anyone trying to build a motor, sensor, or other functional device.

The question that matters is: *will this material actually do what I need it to do?*

For most commercially relevant properties (coercivity in a permanent magnet, catalytic activity, mechanical strength under fatigue) the answer depends on far more than crystal structure. It depends on microstructure: grain size, grain boundaries, defect density, domain structure. And microstructure depends on processing: how you made the material, at what temperature, for how long, in what atmosphere, cooled at what rate. I've measured the same nominal composition — same crystal phase, same stoichiometry — and seen coercivity values vary by orders of magnitude depending on annealing temperature and cooling rate. The crystal structure was identical. The magnetic performance was not.

No atomic prediction model captures this. The multiscale problem, connecting atomic-scale structure to macroscopic device performance, remains unsolved. And better computation alone won't fully resolve it, because simulations are models of reality, not reality itself. Every DFT calculation involves approximations. Every ML potential is trained on that approximate data. You can improve the functional, expand the basis set, add more training data, but it is still a model. The ground truth is always experiment. The real world, not a model of it.

This matters because most AI materials models today are trained on simulated data. Their predictions are bounded by the accuracy of those simulations, regardless of how sophisticated the machine learning becomes. Meanwhile, the experimental data that does exist is sparse, inconsistent, and almost never captures the processing conditions that actually determine performance. Garbage in, garbage out, and at the moment, much of what goes in is approximate.

## The gap is in the data, not the models

Having worked in materials science for some years now, I think there is a profound lack of appreciation for how poor the data situation really is.

Current materials databases tell you *what* exists: crystal structures, formation energies, some electronic properties. They almost never tell you how to make it, what went wrong when it didn't work, or which processing conditions led to which properties in which equipment.

A database entry saying "SmCo₅ has coercivity of 2T" is practically useless without context. What grain size? What annealing treatment? What measurement temperature? What applied field sweep rate? What sample geometry and demagnetisation correction? The property without the provenance is noise dressed up as data.

And then there's all the knowledge that isn't in any database at all. Tacit knowledge, accumulated over years of lab work, that never makes it into papers. Knowing that your tube furnace runs 15°C hot on the left side. Knowing that a particular precursor needs to be dried at 120°C overnight or the whole synthesis fails. Knowing that your SQUID magnetometer gives a slightly different moment depending on where the sample sits in the coil, and that you need to centre it carefully every time or your hysteresis loop is subtly wrong. Knowing which substrate orientation gives you epitaxial growth and which gives you a polycrystalline mess, even though both should work according to the lattice mismatch calculation.

Sometimes the recipe doesn't even exist. When it does, critical details are often deliberately omitted, effectively gating entire research areas to a small number of expert groups.

None of this is in a crystal structure database. None of it is addressed by faster predictions or larger models. And without it, any autonomous system is flying blind.

## What would actually work

The vision of a fully autonomous "self-driving lab", where AI designs experiments, robots execute them, and results feed back, is the obvious direction. There are impressive efforts underway: the A-Lab at Berkeley, Toyota Research Institute's autonomous chemistry platform, and a growing number of academic groups building high-throughput experimental systems.

But automation on its own is not enough. What's needed is a system designed from the ground up with the principle of **full provenance.**

Every experiment should capture everything. Not just the final measurement, but the complete synthesis conditions, equipment state, environmental factors, characterisation parameters, and critically, what didn't work and why. The details most researchers never bother to record, because they don't seem important at the time.

A system built around full provenance can do things that no current approach manages.

It can **self-calibrate**. After a few hundred experiments, the system discovers that position 3 in the furnace consistently runs 7°C above setpoint. Nobody had to tell it; it worked it out from its own data. The same goes for systematic instrument offsets, precursor batch variations, and environmental drift.

It can do **structured failure analysis**. Every failed experiment becomes useful data. Not just "it didn't work," but: the XRD shows an unexpected secondary phase, the transport measurement has a kink at 150K that wasn't there before — which suggests a phase transition in something that shouldn't be there, which points to contamination or an incorrect firing temperature. The next experiment is designed to test that specific hypothesis. Over time, failures become some of the most valuable data in the system.

It enables **transfer across contexts**. Knowledge built in one lab — this class of reaction, in this type of furnace, under these conditions — can transfer to a new setup. The system gradually learns what is universal physics and what is specific to one particular piece of equipment.

And it supports **adaptive reasoning**. Initially, a human experimentalist guides strategy: which material system to explore, what objectives to set, when to change direction. Over time, as experimental knowledge is captured as structured data rather than intuition, more of that reasoning can be shared with optimisation algorithms and, eventually, broader AI systems.

## The real value isn't the lab. It's the dataset.

Here's what I think the field is largely missing: the most valuable output of an autonomous materials lab will not be the individual materials it discovers. It will be the dataset it generates.

A dataset linking composition → processing → structure → properties, with full provenance, across thousands of experiments, including failures. Experimental ground truth, not simulated, not approximated. Measured, in the physical world, with complete context.

This dataset does not exist today. Nobody systematically captures it. And it cannot be generated computationally, because the properties that matter most depend on things like microstructure that can only be properly characterised through experiment.

Whoever builds this first has a compounding advantage. Every experiment makes the next one more informed. Every failure is information that nobody else has. After a thousand runs, you're navigating with a map that everyone else is trying to do without.

## What comes next

The major advances in materials discovery are not just going to come from another prediction model, however powerful. We need physical validation. We need real-world datasets with proper provenance. And we need the infrastructure to generate them.

That means building the full closed loop: experiment design → robotic execution → characterisation → analysis → next experiment. Running autonomously. Learning from every iteration. Capturing everything. Improving with every run. We need to scale experimentation the way we have scaled simulations.

The prediction side of this revolution has happened, and it's been remarkable. The synthesis and data side is what comes next.

I'm working on this problem. If you're thinking about the same space — between what AI can predict and what we can actually make — I would genuinely welcome the conversation.

---

*Sam Holt — Experimental and computational physicist. PhD in magnetism (Warwick), former Marie Curie Fellow (Max Planck Institute Hamburg). Working on autonomous materials discovery.*
