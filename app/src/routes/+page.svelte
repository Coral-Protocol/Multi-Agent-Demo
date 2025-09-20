<script lang="ts">
  import { Search, LoaderCircle } from '@lucide/svelte';
  import SvelteMarkdown from '@humanspeak/svelte-markdown'

  let results: string[] = $state([])
  let query = $state('');

  let loading = $state(false);
</script>
<main class="flex flex-col items-center justify-center pt-64">
  <div class="flex flex-row gap-2 w-[70%] mb-5">
  <input class="input" type="text" placeholder="Input" bind:value={query}/>
    <button type="button" class="btn-icon preset-filled" title="Go" aria-label="Go" onclick={async() => {
      results = [];
      loading = true;
      const res = await fetch(encodeURI(`/search?q=${query}`));
      const data = await res.json();
      results.push(data.result);
      loading = false;
    }}><Search size={18} /></button>
  </div>
  {#if loading}
    <LoaderCircle class="animate-spin mt-20" size={30} />
  {/if}
  <div class="w-[60ch]">
    {#each results as result}
      <SvelteMarkdown source={result} />
    {/each}
  </div>
</main>
