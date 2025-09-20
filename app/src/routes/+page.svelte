<script lang="ts">
  import { Search, LoaderCircle } from '@lucide/svelte';
  import SvelteMarkdown from '@humanspeak/svelte-markdown'



  let source = `
# This is a header

This is a paragraph with **bold** and <em>mixed HTML</em>.

* List item with \`inline code\`
* And a [link](https://svelte.dev)
  * With nested items
  * Supporting full markdown
`

</script>
<main class="flex flex-col items-center justify-center pt-64">
  <h1>Hello from Aggregate!</h1>
  <div class="flex flex-row gap-2 w-[70%]">
    <input class="input" type="text" placeholder="Input" />
    <button type="button" class="btn-icon preset-filled" title="Go" aria-label="Go"><Search size={18} /></button>
  </div>
  <LoaderCircle class="animate-spin mt-20" size={30} />
  {#if source}
    <SvelteMarkdown {source} />
  {/if}
</main>
