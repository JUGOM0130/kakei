<script setup>
const model = defineModel({ type: [Number, String], default: '' })
</script>

<template>
  <input
    v-model="model"
    type="text"
    inputmode="numeric"
    pattern="[0-9]*"
    placeholder="0"
    autocomplete="off"
    class="amount-input"
    @input="model = model.replace(/[^0-9]/g, '')"
  />
</template>

<style scoped>
.amount-input {
  font-size: 1.6rem;
  font-weight: 700;
  text-align: right;
}
</style>
